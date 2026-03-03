"""Tests for app.services.post — create, rate limit, version conflict, delete."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


def _make_post_row(user_id=None, version=1, is_pinned=False, view_count=0):
    """Helper to create a mock post row dict with joined author/category fields."""
    uid = uuid.uuid4() if user_id is None else uuid.UUID(user_id)
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "title": "Test Post",
        "content": "<p>Hello</p>",
        "user_id": uid,
        "category_id": None,
        "sig_id": None,
        "keywords": ["test"],
        "allow_comments": True,
        "version": version,
        "comment_count": 0,
        "is_pinned": is_pinned,
        "view_count": view_count,
        "last_comment_at": None,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "author_id": uid,
        "author_username": "alice",
        "author_display_name": "Alice",
        "author_avatar_url": None,
        "category_name": None,
        "search_vector": None,
    }


class TestCreatePost:
    @patch(
        "app.services.post._atomic_check_and_increment_post_limit",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch("app.repositories.post_repo.get_pool")
    async def test_create_post_success(
        self, mock_get_pool, mock_atomic_limit, mock_pool, mock_conn
    ):
        from app.services.post import create_post

        user_id = str(uuid.uuid4())
        mock_conn.fetchrow.return_value = _make_post_row(user_id=user_id)
        mock_get_pool.return_value = mock_pool

        result = await create_post(user_id, "Title", "Content")
        assert result["title"] == "Test Post"
        mock_atomic_limit.assert_called_once()

    @patch(
        "app.services.post._atomic_check_and_increment_post_limit",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_create_post_rate_limited(self, mock_atomic_limit):
        from app.services.post import create_post

        with pytest.raises(ValueError, match="Daily post limit"):
            await create_post(str(uuid.uuid4()), "Title", "Content")


class TestUpdatePost:
    @patch("app.services.post.get_pool")
    async def test_update_post_version_conflict(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import update_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        current_row = _make_post_row(user_id=user_id, version=3)
        mock_conn.fetchrow.return_value = current_row
        mock_get_pool.return_value = mock_pool

        with pytest.raises(ValueError, match="Version conflict"):
            await update_post(post_id, user_id, title="Updated", expected_version=1)


class TestDeletePost:
    @patch("app.repositories.post_repo.get_pool")
    async def test_delete_post_admin(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        owner_id = uuid.uuid4()

        mock_conn.fetchrow.return_value = {"user_id": owner_id}
        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await soft_delete_post(post_id, user_id, is_admin=True)
        assert result is True

    @patch("app.repositories.post_repo.get_pool")
    async def test_delete_post_owner(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await soft_delete_post(post_id, user_id, is_admin=False)
        assert result is True


class TestPinPost:
    @patch("app.repositories.post_repo.get_pool")
    async def test_pin_post_success(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import pin_post

        post_id = uuid.uuid4()
        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await pin_post(post_id, True)
        assert result is True

    @patch("app.repositories.post_repo.get_pool")
    async def test_pin_post_not_found(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import pin_post

        post_id = uuid.uuid4()
        mock_conn.execute.return_value = "UPDATE 0"
        mock_get_pool.return_value = mock_pool

        result = await pin_post(post_id, True)
        assert result is False


class TestTrendingPosts:
    @patch("app.repositories.post_repo.get_pool")
    async def test_get_trending(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import get_trending_posts

        mock_conn.fetch.return_value = [_make_post_row(), _make_post_row()]
        mock_get_pool.return_value = mock_pool

        result = await get_trending_posts(limit=5, days=7)
        assert len(result) == 2
        assert result[0]["title"] == "Test Post"


class TestGetPostWithView:
    @patch("app.repositories.post_repo.get_pool")
    async def test_get_post_increments_view(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import get_post_by_id

        post_id = uuid.uuid4()
        mock_conn.fetchrow.return_value = _make_post_row()
        mock_get_pool.return_value = mock_pool

        result = await get_post_by_id(post_id, increment_view=True)
        assert result is not None
        assert result["title"] == "Test Post"
        # increment_view_count should have been called (via execute on pool)
        assert mock_conn.execute.call_count >= 1
