"""Tests for co-author service, repo, and endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SVC = "app.services.co_author"
_REPO = "app.repositories.co_author_repo"


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


def _make_co_author_row(post_id=None, user_id=None, status="ACCEPTED"):
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "post_id": post_id or uuid.uuid4(),
        "user_id": user_id or uuid.uuid4(),
        "display_name": "Test User",
        "affiliation": None,
        "orcid": None,
        "is_external": False,
        "status": status,
        "invited_by": uuid.uuid4(),
        "invited_at": now,
        "responded_at": now if status != "PENDING" else None,
        "user_display_name": "Test User",
        "user_avatar_url": None,
    }


# --- Repository tests ---


@pytest.mark.asyncio
async def test_insert_co_author(mock_conn):
    from app.repositories import co_author_repo

    row = _make_co_author_row()
    mock_conn.fetchrow = AsyncMock(return_value=row)
    result = await co_author_repo.insert_co_author(
        mock_conn,
        row["id"],
        row["post_id"],
        row["user_id"],
        "Test",
        None,
        None,
        False,
        "PENDING",
        row["invited_by"],
    )
    assert result["id"] == row["id"]
    mock_conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_find_co_authors_by_post(mock_conn):
    from app.repositories import co_author_repo

    post_id = uuid.uuid4()
    rows = [_make_co_author_row(post_id=post_id) for _ in range(3)]
    mock_conn.fetch = AsyncMock(return_value=rows)
    result = await co_author_repo.find_co_authors_by_post(mock_conn, post_id)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_find_co_authors_batch(mock_conn):
    from app.repositories import co_author_repo

    post_ids = [uuid.uuid4() for _ in range(2)]
    rows = [_make_co_author_row(post_id=pid) for pid in post_ids]
    mock_conn.fetch = AsyncMock(return_value=rows)
    result = await co_author_repo.find_co_authors_batch(mock_conn, post_ids)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_is_accepted_co_author_true(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.fetchval = AsyncMock(return_value=1)
    result = await co_author_repo.is_accepted_co_author(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_is_accepted_co_author_false(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.fetchval = AsyncMock(return_value=None)
    result = await co_author_repo.is_accepted_co_author(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_count_co_authors(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.fetchval = AsyncMock(return_value=5)
    result = await co_author_repo.count_co_authors(mock_conn, uuid.uuid4())
    assert result == 5


@pytest.mark.asyncio
async def test_delete_co_author(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 1")
    result = await co_author_repo.delete_co_author(mock_conn, uuid.uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_delete_co_author_not_found(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 0")
    result = await co_author_repo.delete_co_author(mock_conn, uuid.uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_update_status(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    now = datetime.now(timezone.utc)
    result = await co_author_repo.update_status(mock_conn, uuid.uuid4(), "ACCEPTED", now)
    assert result is True


@pytest.mark.asyncio
async def test_find_pending_invitations_empty(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.fetch = AsyncMock(return_value=[])
    result, total = await co_author_repo.find_pending_invitations(mock_conn, uuid.uuid4(), 1, 20)
    assert result == []
    assert total == 0


@pytest.mark.asyncio
async def test_find_existing_by_user(mock_conn):
    from app.repositories import co_author_repo

    row = _make_co_author_row()
    mock_conn.fetchrow = AsyncMock(return_value=row)
    result = await co_author_repo.find_existing_by_user(mock_conn, row["post_id"], row["user_id"])
    assert result is not None


@pytest.mark.asyncio
async def test_delete_by_user_id(mock_conn):
    from app.repositories import co_author_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 3")
    result = await co_author_repo.delete_by_user_id(mock_conn, uuid.uuid4())
    assert result == 3


# --- Service tests ---


@pytest.mark.asyncio
async def test_service_list_co_authors():
    from app.services.co_author import list_co_authors

    post_id = uuid.uuid4()
    rows = [_make_co_author_row(post_id=post_id)]
    with (
        patch(f"{_SVC}.get_pool") as mock_pool,
        patch(f"{_REPO}.find_co_authors_by_post", new_callable=AsyncMock, return_value=rows),
    ):
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.return_value.acquire.return_value = cm

        result = await list_co_authors(post_id)
        assert len(result) == 1
        assert result[0]["post_id"] == str(post_id)


@pytest.mark.asyncio
async def test_service_list_pending_invitations():
    from app.services.co_author import list_pending_invitations

    user_id = str(uuid.uuid4())
    row = _make_co_author_row(status="PENDING")
    row["post_title"] = "Test Post"
    row["invited_by_name"] = "Inviter"
    with (
        patch(f"{_SVC}.get_pool") as mock_pool,
        patch(
            f"{_REPO}.find_pending_invitations",
            new_callable=AsyncMock,
            return_value=([row], 1),
        ),
    ):
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.return_value.acquire.return_value = cm

        invitations, total = await list_pending_invitations(user_id)
        assert total == 1
        assert len(invitations) == 1


# --- Bug fix tests ---


@pytest.mark.asyncio
async def test_invite_co_author_advisory_lock():
    """H3: invite_co_author wraps count+insert in transaction with pg_advisory_xact_lock."""
    from app.services.co_author import invite_co_author

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    target_user_id = str(uuid.uuid4())

    post_row = {"id": post_id, "user_id": uuid.UUID(user_id), "title": "Test Post"}
    target_row = {"id": uuid.UUID(target_user_id), "display_name": "Target User"}
    co_author_row = _make_co_author_row(post_id=post_id, user_id=uuid.UUID(target_user_id))

    # Track calls to verify advisory lock is called
    execute_calls: list[str] = []
    _original_execute = AsyncMock(return_value="SELECT 1")  # noqa: F841

    async def tracking_execute(query, *args):
        execute_calls.append(query)
        return "SELECT 1"

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=tracking_execute)

    # fetchrow returns post_row first, then target_row, then inviter_row
    conn.fetchrow = AsyncMock(side_effect=[post_row, target_row])

    # transaction context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    # Mock for the second pool.acquire (emit event block)
    inviter_row = {"display_name": "Inviter"}
    conn2 = AsyncMock()
    conn2.fetchrow = AsyncMock(return_value=inviter_row)
    cm2 = AsyncMock()
    cm2.__aenter__ = AsyncMock(return_value=conn2)
    cm2.__aexit__ = AsyncMock(return_value=False)

    pool_calls = [0]

    def get_pool_side_effect():
        pool_calls[0] += 1
        if pool_calls[0] <= 1:
            return pool
        # Return a second pool for the emit block
        pool2 = MagicMock()
        pool2.acquire.return_value = cm2
        return pool2

    with (
        patch(f"{_SVC}.get_pool", side_effect=get_pool_side_effect),
        patch(f"{_SVC}.get_redis") as _mock_redis,  # noqa: F841
        patch(f"{_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set()),
        patch(f"{_REPO}.count_co_authors", new_callable=AsyncMock, return_value=0),
        patch(f"{_REPO}.find_existing_by_user", new_callable=AsyncMock, return_value=None),
        patch(f"{_REPO}.insert_co_author", new_callable=AsyncMock, return_value=co_author_row),
        patch(f"{_SVC}.emit", new_callable=AsyncMock),
    ):
        result = await invite_co_author(post_id, user_id, target_user_id)
        assert result is not None

        # Verify advisory lock was called
        assert any(
            "pg_advisory_xact_lock" in call for call in execute_calls
        ), f"Expected pg_advisory_xact_lock in execute calls, got: {execute_calls}"
        # Verify the lock key contains the post_id
        lock_call = [c for c in execute_calls if "pg_advisory_xact_lock" in c][0]
        assert "hashtext" in lock_call

        # Verify transaction was opened
        conn.transaction.assert_called_once()


@pytest.mark.asyncio
async def test_invite_co_author_bilateral_block():
    """H5: invite_co_author rejects when target has blocked the inviter."""
    from app.core.errors import AppError
    from app.services.co_author import invite_co_author

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    target_user_id = str(uuid.uuid4())

    call_count = [0]

    async def mock_get_blocked(redis, uid):
        call_count[0] += 1
        if uid == user_id:
            return set()  # Inviter hasn't blocked anyone
        if uid == target_user_id:
            return {user_id}  # Target has blocked the inviter
        return set()

    with (
        patch(f"{_SVC}.get_redis") as _mock_redis,  # noqa: F841
        patch(f"{_SVC}.get_blocked_user_ids", side_effect=mock_get_blocked),
    ):
        with pytest.raises(AppError) as exc_info:
            await invite_co_author(post_id, user_id, target_user_id)
        assert exc_info.value.status_code == 403
        assert "SOCIAL_003" in str(exc_info.value.detail)
        # Ensure both directions were checked (inviter + target)
        assert call_count[0] == 2


@pytest.mark.asyncio
async def test_count_co_authors_excludes_rejected(mock_conn):
    """M1: count_co_authors query filters to PENDING and ACCEPTED only."""
    from app.repositories import co_author_repo

    mock_conn.fetchval = AsyncMock(return_value=3)
    post_id = uuid.uuid4()
    result = await co_author_repo.count_co_authors(mock_conn, post_id)
    assert result == 3

    # Verify the query includes the status filter
    call_args = mock_conn.fetchval.call_args
    query = call_args[0][0]
    assert "status IN ('PENDING', 'ACCEPTED')" in query
    assert "post_id = $1" in query


@pytest.mark.asyncio
async def test_invite_event_includes_inviter_id():
    """M6: co_author.invited event includes inviter_id for trigger_user_id."""
    from app.services.co_author import invite_co_author

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    target_user_id = str(uuid.uuid4())

    post_row = {"id": post_id, "user_id": uuid.UUID(user_id), "title": "Test Post"}
    target_row = {"id": uuid.UUID(target_user_id), "display_name": "Target User"}
    co_author_row = _make_co_author_row(post_id=post_id, user_id=uuid.UUID(target_user_id))

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[post_row, target_row])

    # transaction context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    # Second pool for emit block
    inviter_row = {"display_name": "Inviter"}
    conn2 = AsyncMock()
    conn2.fetchrow = AsyncMock(return_value=inviter_row)
    cm2 = AsyncMock()
    cm2.__aenter__ = AsyncMock(return_value=conn2)
    cm2.__aexit__ = AsyncMock(return_value=False)

    pool_calls = [0]

    def get_pool_side_effect():
        pool_calls[0] += 1
        if pool_calls[0] <= 1:
            return pool
        pool2 = MagicMock()
        pool2.acquire.return_value = cm2
        return pool2

    mock_emit = AsyncMock()

    with (
        patch(f"{_SVC}.get_pool", side_effect=get_pool_side_effect),
        patch(f"{_SVC}.get_redis") as _mock_redis,  # noqa: F841
        patch(f"{_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set()),
        patch(f"{_REPO}.count_co_authors", new_callable=AsyncMock, return_value=0),
        patch(f"{_REPO}.find_existing_by_user", new_callable=AsyncMock, return_value=None),
        patch(f"{_REPO}.insert_co_author", new_callable=AsyncMock, return_value=co_author_row),
        patch(f"{_SVC}.emit", mock_emit),
    ):
        await invite_co_author(post_id, user_id, target_user_id)

        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs["inviter_id"] == user_id
        assert call_kwargs["target_user_id"] == target_user_id


def test_no_dead_code_if_false():
    """L4: co_author.py should not contain 'if False' dead code blocks."""
    import inspect

    from app.services import co_author

    source = inspect.getsource(co_author)
    assert "if False" not in source, "Dead code 'if False' block found in co_author.py"


# --- B3: Service functions no longer accept pool parameter ---


def test_invite_co_author_no_pool_parameter():
    """B3: invite_co_author no longer has pool parameter."""
    import inspect

    from app.services.co_author import invite_co_author

    sig = inspect.signature(invite_co_author)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


def test_add_external_co_author_no_pool_parameter():
    """B3: add_external_co_author no longer has pool parameter."""
    import inspect

    from app.services.co_author import add_external_co_author

    sig = inspect.signature(add_external_co_author)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


def test_respond_to_invitation_no_pool_parameter():
    """B3: respond_to_invitation no longer has pool parameter."""
    import inspect

    from app.services.co_author import respond_to_invitation

    sig = inspect.signature(respond_to_invitation)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "co_author_id", "First parameter should be co_author_id"


def test_remove_co_author_no_pool_parameter():
    """B3: remove_co_author no longer has pool parameter."""
    import inspect

    from app.services.co_author import remove_co_author

    sig = inspect.signature(remove_co_author)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


def test_list_co_authors_no_pool_parameter():
    """B3: list_co_authors no longer has pool parameter."""
    import inspect

    from app.services.co_author import list_co_authors

    sig = inspect.signature(list_co_authors)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


def test_list_pending_invitations_no_pool_parameter():
    """B3: list_pending_invitations no longer has pool parameter."""
    import inspect

    from app.services.co_author import list_pending_invitations

    sig = inspect.signature(list_pending_invitations)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "user_id", "First parameter should be user_id"
