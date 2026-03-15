"""Tests for comment bug fixes: B1 (find_by_id is_deleted filter) and B18 (self-reference guard)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFindByIdExcludesDeleted:
    """B1: comment_repo.find_by_id must filter out soft-deleted comments."""

    @pytest.mark.anyio
    async def test_find_by_id_excludes_deleted(self, mock_pool, mock_conn):
        """find_by_id SQL query must contain 'is_deleted = false'."""
        comment_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            from app.repositories.comment_repo import find_by_id

            result = await find_by_id(comment_id)

        assert result is None
        call_args = mock_conn.fetchrow.call_args
        sql = call_args[0][0]
        assert "is_deleted = false" in sql
        assert "cm.id = $1" in sql


class TestSelfReferencingCommentRejected:
    """B18: create_comment must reject parent_id == comment_id."""

    @pytest.mark.anyio
    async def test_self_referencing_comment_rejected(self):
        """create_comment raises ValueError when parent_id equals the generated comment_id."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        # We patch uuid.uuid4 in the service module to control the generated comment_id,
        # then pass that same id as parent_id.
        fixed_id = uuid.uuid4()

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch("app.services.comment.uuid.uuid4", return_value=fixed_id),
            patch("app.services.comment.get_pool", return_value=MagicMock()),
            patch(
                "app.repositories.post_repo.find_owner_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.comment.get_redis", return_value=mock_redis),
        ):
            from app.services.comment import create_comment

            with pytest.raises(ValueError, match="cannot reply to itself"):
                await create_comment(
                    post_id=post_id,
                    user_id=user_id,
                    content="Self-reply attempt",
                    parent_id=str(fixed_id),
                )
