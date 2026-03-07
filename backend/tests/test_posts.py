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


class TestSearchRepo:
    @patch("app.repositories.post_repo.get_pool")
    async def test_search_uses_websearch_to_tsquery(self, mock_get_pool, mock_pool, mock_conn):
        """search() should use websearch_to_tsquery, not to_tsquery."""
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword="hello world")
        # Verify the SQL uses websearch_to_tsquery
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "websearch_to_tsquery" in sql
        assert "to_tsquery" not in sql.replace("websearch_to_tsquery", "")

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_or_logic(self, mock_get_pool, mock_pool, mock_conn):
        """search() with logic=OR should join terms with OR."""
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword="AI learning", logic="OR")
        call_args = mock_conn.fetch.call_args
        # The second positional arg is the keyword param
        keyword_param = call_args[0][1]
        assert "OR" in keyword_param


class TestFindHistory:
    @patch("app.repositories.post_repo.get_pool")
    async def test_find_history_default_limit(self, mock_get_pool, mock_pool, mock_conn):
        """find_history() should pass LIMIT $2 with default limit=50."""
        from app.repositories.post_repo import find_history

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        post_id = uuid.uuid4()
        await find_history(post_id)

        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "LIMIT $2" in sql
        # Default limit=50 should be the second positional arg
        assert call_args[0][2] == 50

    @patch("app.repositories.post_repo.get_pool")
    async def test_find_history_custom_limit(self, mock_get_pool, mock_pool, mock_conn):
        """find_history(limit=10) should pass limit=10."""
        from app.repositories.post_repo import find_history

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        post_id = uuid.uuid4()
        await find_history(post_id, limit=10)

        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "LIMIT $2" in sql
        assert call_args[0][2] == 10

    @patch("app.repositories.post_repo.get_pool")
    async def test_find_history_returns_dicts(self, mock_get_pool, mock_pool, mock_conn):
        """find_history() should return list of dicts from rows."""
        from app.repositories.post_repo import find_history

        fake_row = {
            "id": uuid.uuid4(),
            "post_id": uuid.uuid4(),
            "version": 1,
            "title": "V1",
            "content": "body",
        }
        mock_conn.fetch.return_value = [fake_row]
        mock_get_pool.return_value = mock_pool

        result = await find_history(uuid.uuid4())
        assert len(result) == 1
        assert result[0]["title"] == "V1"
