"""Tests for form response race condition fix — atomic INSERT with max_respondents
check in a single query, preventing concurrent over-insertion."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_REPO = "app.repositories.form_repo"
_SVC = "app.services.form"


def _find_by_id_mock(form_row):
    """Return a mock for form_repo.find_by_id that returns the given row."""
    return patch(
        f"{_SVC}.form_repo.find_by_id",
        new_callable=AsyncMock,
        return_value=(form_row, 0),
    )


def _make_form_row(
    form_id=None,
    sig_id=None,
    max_respondents=None,
    deadline=None,
    allow_non_members=False,
    is_schema_locked=False,
):
    """Create a fake form row dict as returned by find_for_update."""
    return {
        "id": form_id or uuid.uuid4(),
        "sig_id": sig_id or uuid.uuid4(),
        "created_by": uuid.uuid4(),
        "title": "Test Form",
        "description": None,
        "banner_url": None,
        "deadline": deadline,
        "max_respondents": max_respondents,
        "questions": json.dumps([{"id": "q1", "type": "text", "label": "Name", "required": True}]),
        "is_schema_locked": is_schema_locked,
        "is_deleted": False,
        "allow_non_members": allow_non_members,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


class TestInsertResponseAtomic:
    """Test form_repo.insert_response with max_respondents enforcement."""

    @pytest.mark.anyio
    async def test_insert_without_max_uses_plain_insert(self, mock_conn):
        """When max_respondents is None, use a plain INSERT."""
        from app.repositories import form_repo

        rid = uuid.uuid4()
        fid = uuid.uuid4()
        uid = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

        result = await form_repo.insert_response(
            rid, fid, uid, {"q1": "answer"}, mock_conn, max_respondents=None
        )

        assert result is True
        # Without max_respondents, advisory lock should NOT be called
        for call in mock_conn.execute.call_args_list:
            query = call[0][0]
            assert "pg_advisory_xact_lock" not in query
        call_args = mock_conn.execute.call_args
        query = call_args[0][0]
        assert "VALUES" in query
        assert "SELECT" not in query or "SELECT $1" not in query

    @pytest.mark.anyio
    async def test_insert_with_max_uses_atomic_subquery(self, mock_conn):
        """When max_respondents is set, use INSERT ... SELECT with count check."""
        from app.repositories import form_repo

        rid = uuid.uuid4()
        fid = uuid.uuid4()
        uid = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

        result = await form_repo.insert_response(
            rid, fid, uid, {"q1": "answer"}, mock_conn, max_respondents=10
        )

        assert result is True
        # First call should be the advisory lock
        lock_call = mock_conn.execute.call_args_list[0]
        assert "pg_advisory_xact_lock" in lock_call[0][0]
        # Second call should be the INSERT...SELECT
        insert_call = mock_conn.execute.call_args_list[1]
        query = insert_call[0][0]
        assert "SELECT" in query
        assert "COUNT(*)" in query
        # max_respondents should be the 5th parameter
        assert insert_call[0][5] == 10

    @pytest.mark.anyio
    async def test_insert_returns_false_when_limit_reached(self, mock_conn):
        """When the atomic INSERT inserts 0 rows, return False."""
        from app.repositories import form_repo

        rid = uuid.uuid4()
        fid = uuid.uuid4()
        uid = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 0")

        result = await form_repo.insert_response(
            rid, fid, uid, {"q1": "answer"}, mock_conn, max_respondents=5
        )

        assert result is False

    @pytest.mark.anyio
    async def test_advisory_lock_uses_form_id(self, mock_conn):
        """Verify the advisory lock call passes str(form_id)."""
        from app.repositories import form_repo

        rid = uuid.uuid4()
        fid = uuid.uuid4()
        uid = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

        await form_repo.insert_response(
            rid, fid, uid, {"q1": "answer"}, mock_conn, max_respondents=10
        )

        lock_call = mock_conn.execute.call_args_list[0]
        assert "pg_advisory_xact_lock" in lock_call[0][0]
        assert lock_call[0][1] == str(fid)


class TestSubmitResponseService:
    """Test the service-layer submit_response with atomic max_respondents."""

    @pytest.mark.anyio
    async def test_submit_success_with_max_respondents(self):
        """submit_response succeeds when atomic insert returns True."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form_row = _make_form_row(form_id=form_id, max_respondents=10, allow_non_members=True)

        mock_conn = AsyncMock()
        mock_conn.transaction = MagicMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction.return_value = tx

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            _find_by_id_mock(form_row),
            patch(
                f"{_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=form_row,
            ),
            patch(
                f"{_SVC}.form_repo.check_duplicate_response",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                f"{_SVC}.form_repo.insert_response",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_insert,
            patch(
                f"{_SVC}.form_repo.lock_schema",
                new_callable=AsyncMock,
            ),
        ):
            result = await (await _import_submit())(form_id, user_id, {"q1": "answer"})

        assert result["message"] == "Response submitted successfully."
        # Verify max_respondents was passed to insert_response
        mock_insert.assert_called_once()
        call_kwargs = mock_insert.call_args
        assert call_kwargs.kwargs.get("max_respondents") == 10

    @pytest.mark.anyio
    async def test_submit_fails_when_max_reached(self):
        """submit_response raises ValueError when atomic insert returns False."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form_row = _make_form_row(form_id=form_id, max_respondents=5, allow_non_members=True)

        mock_conn = AsyncMock()
        mock_conn.transaction = MagicMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction.return_value = tx

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            _find_by_id_mock(form_row),
            patch(
                f"{_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=form_row,
            ),
            patch(
                f"{_SVC}.form_repo.check_duplicate_response",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                f"{_SVC}.form_repo.insert_response",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            with pytest.raises(ValueError, match="maximum number of responses"):
                await (await _import_submit())(form_id, user_id, {"q1": "answer"})

    @pytest.mark.anyio
    async def test_submit_no_max_respondents_passes_none(self):
        """When form has no max_respondents, None is passed to insert_response."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form_row = _make_form_row(form_id=form_id, max_respondents=None, allow_non_members=True)

        mock_conn = AsyncMock()
        mock_conn.transaction = MagicMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction.return_value = tx

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            _find_by_id_mock(form_row),
            patch(
                f"{_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=form_row,
            ),
            patch(
                f"{_SVC}.form_repo.check_duplicate_response",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                f"{_SVC}.form_repo.insert_response",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_insert,
            patch(
                f"{_SVC}.form_repo.lock_schema",
                new_callable=AsyncMock,
            ),
        ):
            await (await _import_submit())(form_id, user_id, {"q1": "answer"})

        mock_insert.assert_called_once()
        assert mock_insert.call_args.kwargs.get("max_respondents") is None

    @pytest.mark.anyio
    async def test_submit_no_separate_count_check(self):
        """Verify count_responses is NOT called during submit (removed in favor of atomic)."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form_row = _make_form_row(form_id=form_id, max_respondents=10, allow_non_members=True)

        mock_conn = AsyncMock()
        mock_conn.transaction = MagicMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction.return_value = tx

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            _find_by_id_mock(form_row),
            patch(
                f"{_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=form_row,
            ),
            patch(
                f"{_SVC}.form_repo.check_duplicate_response",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                f"{_SVC}.form_repo.insert_response",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                f"{_SVC}.form_repo.count_responses",
                new_callable=AsyncMock,
            ) as mock_count,
            patch(
                f"{_SVC}.form_repo.lock_schema",
                new_callable=AsyncMock,
            ),
        ):
            await (await _import_submit())(form_id, user_id, {"q1": "answer"})

        # count_responses should NOT be called during submit_response anymore
        mock_count.assert_not_called()


class TestDuplicateResponseAdvisoryLock:
    """Test the advisory lock on (form_id, user_id) prevents TOCTOU duplicate responses."""

    @pytest.mark.anyio
    async def test_duplicate_response_advisory_lock_called(self):
        """Verify pg_advisory_xact_lock is called with a key containing both
        form_id and user_id BEFORE the duplicate check."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form_row = _make_form_row(form_id=form_id, allow_non_members=True)

        mock_conn = AsyncMock()
        mock_conn.transaction = MagicMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction.return_value = tx

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        # Track call order to verify lock happens before duplicate check
        call_order = []

        async def track_execute(query, *args):
            if "pg_advisory_xact_lock" in query:
                call_order.append("advisory_lock")
            return "INSERT 0 1"

        mock_conn.execute = AsyncMock(side_effect=track_execute)

        async def track_check_dup(*args, **kwargs):
            call_order.append("check_duplicate")
            return False

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            _find_by_id_mock(form_row),
            patch(
                f"{_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=form_row,
            ),
            patch(
                f"{_SVC}.form_repo.check_duplicate_response",
                new_callable=AsyncMock,
                side_effect=track_check_dup,
            ),
            patch(
                f"{_SVC}.form_repo.insert_response",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                f"{_SVC}.form_repo.lock_schema",
                new_callable=AsyncMock,
            ),
        ):
            await (await _import_submit())(form_id, user_id, {"q1": "answer"})

        # Advisory lock must be called BEFORE duplicate check
        assert call_order.index("advisory_lock") < call_order.index("check_duplicate")

        # Verify the lock key contains both form_id and user_id
        lock_call = mock_conn.execute.call_args_list[0]
        assert "pg_advisory_xact_lock" in lock_call[0][0]
        lock_key = lock_call[0][1]
        assert str(form_id) in lock_key
        assert user_id in lock_key

    @pytest.mark.anyio
    async def test_advisory_lock_key_differs_per_user(self):
        """Different users get different advisory lock keys for the same form."""
        form_id = uuid.uuid4()
        user_id_a = str(uuid.uuid4())
        user_id_b = str(uuid.uuid4())

        lock_keys = []

        for user_id in [user_id_a, user_id_b]:
            form_row = _make_form_row(form_id=form_id, allow_non_members=True)

            mock_conn = AsyncMock()
            mock_conn.transaction = MagicMock()
            tx = AsyncMock()
            tx.__aenter__ = AsyncMock(return_value=tx)
            tx.__aexit__ = AsyncMock(return_value=False)
            mock_conn.transaction.return_value = tx

            mock_pool = MagicMock()
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_conn)
            cm.__aexit__ = AsyncMock(return_value=False)
            mock_pool.acquire.return_value = cm

            with (
                patch(f"{_SVC}.get_pool", return_value=mock_pool),
                _find_by_id_mock(form_row),
                patch(
                    f"{_SVC}.form_repo.find_for_update",
                    new_callable=AsyncMock,
                    return_value=form_row,
                ),
                patch(
                    f"{_SVC}.form_repo.check_duplicate_response",
                    new_callable=AsyncMock,
                    return_value=False,
                ),
                patch(
                    f"{_SVC}.form_repo.insert_response",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_SVC}.form_repo.lock_schema",
                    new_callable=AsyncMock,
                ),
            ):
                await (await _import_submit())(form_id, user_id, {"q1": "answer"})

            # First execute call is the advisory lock
            lock_call = mock_conn.execute.call_args_list[0]
            lock_keys.append(lock_call[0][1])

        # Lock keys must be different for different users
        assert lock_keys[0] != lock_keys[1]
        # But both contain the same form_id
        assert str(form_id) in lock_keys[0]
        assert str(form_id) in lock_keys[1]


async def _import_submit():
    """Lazy import to avoid import-time side effects."""
    from app.services.form import submit_response

    return submit_response
