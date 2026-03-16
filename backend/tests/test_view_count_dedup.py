"""Tests for Bug #6: View count dedup — duplicate views within 5 min don't increment."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestViewCountDedup:
    """Test that get_post_by_id deduplicates view increments via Redis."""

    @pytest.mark.anyio
    async def test_first_view_increments(self):
        """First view from a user should set Redis key and increment count."""
        post_id = uuid.uuid4()
        viewer_id = str(uuid.uuid4())
        fake_row = {"id": post_id, "title": "Test", "user_id": uuid.uuid4()}
        fake_post = {"id": str(post_id), "title": "Test"}

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)  # nx=True returns True (key was new)
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch(
                "app.services.post.post_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=fake_row,
            ),
            patch(
                "app.services.post.post_repo.increment_view_count", new_callable=AsyncMock
            ) as mock_incr,
            patch("app.services.post.get_redis", return_value=mock_redis),
            patch("app.services.post.get_pool", return_value=MagicMock()),
            patch(
                "app.services.post.async_row_to_post",
                new_callable=AsyncMock,
                return_value=fake_post,
            ),
        ):
            from app.services.post import get_post_by_id

            result = await get_post_by_id(post_id, increment_view=True, viewer_id=viewer_id)

        assert result == fake_post
        mock_redis.set.assert_awaited_once_with(
            f"viewed:{post_id}:{viewer_id}", "1", ex=86400, nx=True
        )
        mock_incr.assert_awaited_once_with(post_id)

    @pytest.mark.anyio
    async def test_duplicate_view_does_not_increment(self):
        """Second view within 5 min should NOT increment (Redis returns None/False)."""
        post_id = uuid.uuid4()
        viewer_id = str(uuid.uuid4())
        fake_row = {"id": post_id, "title": "Test", "user_id": uuid.uuid4()}
        fake_post = {"id": str(post_id), "title": "Test"}

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=None)  # nx=True returns None (key exists)
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch(
                "app.services.post.post_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=fake_row,
            ),
            patch(
                "app.services.post.post_repo.increment_view_count", new_callable=AsyncMock
            ) as mock_incr,
            patch("app.services.post.get_redis", return_value=mock_redis),
            patch("app.services.post.get_pool", return_value=MagicMock()),
            patch(
                "app.services.post.async_row_to_post",
                new_callable=AsyncMock,
                return_value=fake_post,
            ),
        ):
            from app.services.post import get_post_by_id

            result = await get_post_by_id(post_id, increment_view=True, viewer_id=viewer_id)

        assert result == fake_post
        mock_redis.set.assert_awaited_once()
        mock_incr.assert_not_awaited()

    @pytest.mark.anyio
    async def test_no_viewer_id_always_increments(self):
        """Backward compat: no viewer_id → always increment (no Redis check)."""
        post_id = uuid.uuid4()
        fake_row = {"id": post_id, "title": "Test", "user_id": uuid.uuid4()}
        fake_post = {"id": str(post_id), "title": "Test"}

        with (
            patch(
                "app.services.post.post_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=fake_row,
            ),
            patch(
                "app.services.post.post_repo.increment_view_count", new_callable=AsyncMock
            ) as mock_incr,
            patch("app.services.post.get_redis") as mock_get_redis,
            patch(
                "app.services.post.async_row_to_post",
                new_callable=AsyncMock,
                return_value=fake_post,
            ),
        ):
            from app.services.post import get_post_by_id

            result = await get_post_by_id(post_id, increment_view=True, viewer_id=None)

        assert result == fake_post
        mock_incr.assert_awaited_once_with(post_id)
        mock_get_redis.assert_not_called()

    @pytest.mark.anyio
    async def test_no_increment_flag(self):
        """increment_view=False should skip view count entirely."""
        post_id = uuid.uuid4()
        fake_row = {"id": post_id, "title": "Test", "user_id": uuid.uuid4()}
        fake_post = {"id": str(post_id), "title": "Test"}

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch(
                "app.services.post.post_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=fake_row,
            ),
            patch(
                "app.services.post.post_repo.increment_view_count", new_callable=AsyncMock
            ) as mock_incr,
            patch("app.services.post.get_redis", return_value=mock_redis),
            patch("app.services.post.get_pool", return_value=MagicMock()),
            patch(
                "app.services.post.async_row_to_post",
                new_callable=AsyncMock,
                return_value=fake_post,
            ),
        ):
            from app.services.post import get_post_by_id

            result = await get_post_by_id(
                post_id, increment_view=False, viewer_id=str(uuid.uuid4())
            )

        assert result == fake_post
        mock_incr.assert_not_awaited()

    @pytest.mark.anyio
    async def test_post_not_found(self):
        """Non-existent post returns None without touching Redis."""
        post_id = uuid.uuid4()

        with (
            patch(
                "app.services.post.post_repo.find_by_id", new_callable=AsyncMock, return_value=None
            ),
            patch(
                "app.services.post.post_repo.increment_view_count", new_callable=AsyncMock
            ) as mock_incr,
            patch("app.services.post.get_redis") as mock_get_redis,
        ):
            from app.services.post import get_post_by_id

            result = await get_post_by_id(post_id, increment_view=True, viewer_id=str(uuid.uuid4()))

        assert result is None
        mock_incr.assert_not_awaited()
        mock_get_redis.assert_not_called()


class TestEndpointPassesViewerId:
    """Test that the GET /posts/{post_id} endpoint passes viewer_id."""

    @pytest.mark.anyio
    async def test_get_post_passes_viewer_id(self, client):
        """GET /posts/{id} should pass current_user sub as viewer_id."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        fake_post = {
            "id": str(post_id),
            "title": "Test",
            "content": "<p>Body</p>",
            "author": {"id": user_id, "username": "u", "display_name": "U", "avatar_url": None},
            "category_id": None,
            "category_name": None,
            "keywords": [],
            "allow_comments": True,
            "version": 1,
            "comment_count": 0,
            "view_count": 1,
            "is_pinned": False,
            "reactions": None,
            "last_comment_at": None,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": user_id, "role": "MEMBER", "jti": str(uuid.uuid4())}
        app.dependency_overrides[get_current_user] = lambda: payload

        try:
            with patch(
                "app.api.v1.endpoints.posts.get_post_by_id",
                new_callable=AsyncMock,
                return_value=fake_post,
            ) as mock_get:
                resp = await client.get(f"/api/v1/posts/{post_id}")
                assert resp.status_code == 200
                mock_get.assert_awaited_once_with(post_id, increment_view=True, viewer_id=user_id)
        finally:
            app.dependency_overrides.clear()
