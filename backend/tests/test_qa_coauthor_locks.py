"""Tests for QA vote transaction safety and co-author advisory locks."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.constants import MAX_CO_AUTHORS_PER_POST
from app.core.errors import AppError

_POST_ID = uuid.uuid4()
_COMMENT_ID = uuid.uuid4()
_USER_ID = str(uuid.uuid4())
_OWNER_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# H5: vote_on_answer uses transaction with FOR UPDATE
# ---------------------------------------------------------------------------


class TestVoteOnAnswerTransaction:
    @pytest.mark.anyio
    async def test_vote_on_answer_uses_transaction_with_for_update(self, mock_pool, mock_conn):
        """vote_on_answer must SELECT the comment inside a transaction with FOR UPDATE."""
        comment_row = {
            "id": _COMMENT_ID,
            "user_id": uuid.uuid4(),
            "post_id": _POST_ID,
            "post_type": "question",
        }
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                comment_row,  # comment SELECT inside transaction
                {"vote_score": 1},  # from upsert_vote
            ]
        )

        with (
            patch("app.services.qa.get_pool", return_value=mock_pool),
            patch("app.services.qa.check_rate_limit", new_callable=AsyncMock, return_value=True),
        ):
            from app.services.qa import vote_on_answer

            await vote_on_answer(_COMMENT_ID, _USER_ID, 1)

        # Transaction must have been opened
        mock_conn.transaction.assert_called_once()

        # The first fetchrow call (comment SELECT) must contain FOR UPDATE
        first_call = mock_conn.fetchrow.call_args_list[0]
        sql = first_call[0][0]
        assert (
            "FOR UPDATE" in sql
        ), "Comment SELECT must use FOR UPDATE to prevent concurrent deletion"

    @pytest.mark.anyio
    async def test_vote_on_answer_rejects_deleted_comment(self, mock_pool, mock_conn):
        """vote_on_answer raises NotFoundError when comment not found."""
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with (
            patch("app.services.qa.get_pool", return_value=mock_pool),
            patch("app.services.qa.check_rate_limit", new_callable=AsyncMock, return_value=True),
        ):
            from app.services.qa import vote_on_answer

            with pytest.raises(AppError) as exc_info:
                await vote_on_answer(_COMMENT_ID, _USER_ID, 1)

            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# H8: add_external_co_author uses advisory lock
# ---------------------------------------------------------------------------


class TestAddExternalCoAuthorLock:
    @pytest.mark.anyio
    async def test_add_external_co_author_uses_advisory_lock(self, mock_pool, mock_conn):
        """add_external_co_author must acquire pg_advisory_xact_lock before count check."""
        post_row = {"id": _POST_ID, "user_id": uuid.UUID(_OWNER_ID)}
        co_author_row = {
            "id": uuid.uuid4(),
            "post_id": _POST_ID,
            "user_id": None,
            "display_name": "External Author",
            "affiliation": None,
            "orcid": None,
            "is_external": True,
            "status": "ACCEPTED",
            "invited_by": uuid.UUID(_OWNER_ID),
            "created_at": None,
            "updated_at": None,
            "responded_at": None,
        }

        mock_conn.fetchrow = AsyncMock(return_value=post_row)

        with (
            patch("app.services.co_author.get_pool", return_value=mock_pool),
            patch(
                "app.services.co_author.co_author_repo.count_co_authors",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "app.services.co_author.co_author_repo.insert_co_author",
                new_callable=AsyncMock,
                return_value=co_author_row,
            ),
            patch(
                "app.converters.co_author_converter.to_co_author_response",
                new_callable=AsyncMock,
                return_value={"id": str(co_author_row["id"])},
            ),
        ):
            from app.services.co_author import add_external_co_author

            await add_external_co_author(_POST_ID, _OWNER_ID, "External Author")

        # Transaction must have been opened
        mock_conn.transaction.assert_called_once()

        # Advisory lock must have been called with the post_id
        execute_calls = mock_conn.execute.call_args_list
        advisory_calls = [c for c in execute_calls if "pg_advisory_xact_lock" in str(c)]
        assert len(advisory_calls) == 1, "Must acquire pg_advisory_xact_lock inside transaction"
        assert str(_POST_ID) in str(advisory_calls[0]), "Advisory lock must use post_id"

    @pytest.mark.anyio
    async def test_add_external_co_author_enforces_count_limit(self, mock_pool, mock_conn):
        """add_external_co_author raises when MAX_CO_AUTHORS_PER_POST is reached."""
        post_row = {"id": _POST_ID, "user_id": uuid.UUID(_OWNER_ID)}
        mock_conn.fetchrow = AsyncMock(return_value=post_row)

        with (
            patch("app.services.co_author.get_pool", return_value=mock_pool),
            patch(
                "app.services.co_author.co_author_repo.count_co_authors",
                new_callable=AsyncMock,
                return_value=MAX_CO_AUTHORS_PER_POST,
            ),
        ):
            from app.services.co_author import add_external_co_author

            with pytest.raises(AppError) as exc_info:
                await add_external_co_author(_POST_ID, _OWNER_ID, "External Author")

            assert exc_info.value.status_code == 400
            assert "Maximum co-authors" in str(exc_info.value.detail)

    @pytest.mark.anyio
    async def test_advisory_lock_acquired_before_count_check(self, mock_pool, mock_conn):
        """Advisory lock must be acquired before the count check to prevent races."""
        post_row = {"id": _POST_ID, "user_id": uuid.UUID(_OWNER_ID)}
        mock_conn.fetchrow = AsyncMock(return_value=post_row)

        call_order: list[str] = []

        async def mock_execute(sql, *args, **kwargs):
            if "pg_advisory_xact_lock" in sql:
                call_order.append("advisory_lock")
            return "UPDATE 1"

        async def mock_count(*args, **kwargs):
            call_order.append("count_check")
            return MAX_CO_AUTHORS_PER_POST  # trigger limit to stop early

        mock_conn.execute = AsyncMock(side_effect=mock_execute)

        with (
            patch("app.services.co_author.get_pool", return_value=mock_pool),
            patch(
                "app.services.co_author.co_author_repo.count_co_authors",
                new_callable=AsyncMock,
                side_effect=mock_count,
            ),
        ):
            from app.services.co_author import add_external_co_author

            with pytest.raises(AppError):
                await add_external_co_author(_POST_ID, _OWNER_ID, "External Author")

        assert call_order == [
            "advisory_lock",
            "count_check",
        ], "Advisory lock must be acquired before count check"
