"""Tests for category deletion FK handling — verifies posts.category_id is set
to NULL before the category row is deleted (transactional safety)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_REPO = "app.repositories.category_repo"


class TestCategoryDeleteNullifiesPosts:
    """Verify that category_repo.delete() nullifies posts before deleting."""

    @pytest.mark.anyio
    async def test_delete_nullifies_posts_then_deletes(self, mock_pool, mock_conn):
        """DELETE category should SET posts.category_id = NULL then DELETE category."""
        cat_id = uuid.uuid4()
        call_order: list[str] = []

        async def track_execute(query, *args):
            if "UPDATE posts" in query:
                call_order.append("nullify_posts")
            elif "DELETE FROM categories" in query:
                call_order.append("delete_category")
            return "DELETE 1"

        mock_conn.execute = AsyncMock(side_effect=track_execute)

        from app.repositories import category_repo

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await category_repo.delete(cat_id)

        assert result is True
        assert call_order == ["nullify_posts", "delete_category"]

    @pytest.mark.anyio
    async def test_delete_runs_in_transaction(self, mock_pool, mock_conn):
        """DELETE category should use a transaction for atomicity."""
        cat_id = uuid.uuid4()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        from app.repositories import category_repo

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            await category_repo.delete(cat_id)

        # transaction() should have been called
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_delete_passes_category_id_to_nullify(self, mock_pool, mock_conn):
        """The UPDATE posts query should use the correct category_id parameter."""
        cat_id = uuid.uuid4()
        captured_args: list[tuple] = []

        async def capture_execute(query, *args):
            captured_args.append((query, args))
            return "DELETE 1"

        mock_conn.execute = AsyncMock(side_effect=capture_execute)

        from app.repositories import category_repo

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            await category_repo.delete(cat_id)

        # First call: UPDATE posts SET category_id = NULL WHERE category_id = $1
        assert len(captured_args) == 2
        nullify_query, nullify_args = captured_args[0]
        assert "UPDATE posts" in nullify_query
        assert "category_id = NULL" in nullify_query
        assert nullify_args == (cat_id,)

        # Second call: DELETE FROM categories WHERE id = $1
        delete_query, delete_args = captured_args[1]
        assert "DELETE FROM categories" in delete_query
        assert delete_args == (cat_id,)

    @pytest.mark.anyio
    async def test_delete_returns_false_when_not_found(self, mock_pool, mock_conn):
        """DELETE category returns False when no category row was deleted."""
        cat_id = uuid.uuid4()

        call_count = 0

        async def execute_side_effect(query, *args):
            nonlocal call_count
            call_count += 1
            if "DELETE FROM categories" in query:
                return "DELETE 0"
            return "UPDATE 0"

        mock_conn.execute = AsyncMock(side_effect=execute_side_effect)

        from app.repositories import category_repo

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await category_repo.delete(cat_id)

        assert result is False
