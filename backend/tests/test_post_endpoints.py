"""Tests for posts endpoints — create, search, get, not-found, update, history."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.posts"


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


def _make_post(post_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(post_id or uuid.uuid4()),
        "title": "Test Post",
        "content": "<p>Body</p>",
        "author": {
            "id": uid,
            "username": "testuser",
            "display_name": "Test User",
            "avatar_url": None,
        },
        "category_id": None,
        "category_name": None,
        "keywords": ["test"],
        "allow_comments": True,
        "version": 1,
        "comment_count": 0,
        "created_at": now,
        "updated_at": now,
    }


class TestCreatePost:
    @pytest.mark.anyio
    async def test_create_post(self, client):
        """POST /posts → 201."""
        user_id = str(uuid.uuid4())
        post = _make_post(user_id=user_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP}.create_post", new_callable=AsyncMock, return_value=post):
                resp = await client.post(
                    "/api/v1/posts",
                    json={"title": "Test Post", "content": "<p>Body</p>"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["title"] == "Test Post"
        finally:
            _clear_overrides()


class TestSearchPosts:
    @pytest.mark.anyio
    async def test_search_posts(self, client):
        """POST /posts/search → 200."""
        post = _make_post()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.search_posts", new_callable=AsyncMock, return_value=([post], 1, 1)):
                resp = await client.post(
                    "/api/v1/posts/search",
                    json={"keyword": "test"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()


class TestSearchPostsSpecialChars:
    @pytest.mark.anyio
    async def test_search_with_special_chars(self, client):
        """POST /posts/search with special tsquery chars → 200 (no crash)."""
        post = _make_post()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.search_posts",
                new_callable=AsyncMock,
                return_value=([post], 1, 1),
            ):
                resp = await client.post(
                    "/api/v1/posts/search",
                    json={"keyword": "hello & world | foo (bar)"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_search_with_or_logic(self, client):
        """POST /posts/search with logic=OR → 200."""
        post = _make_post()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.search_posts",
                new_callable=AsyncMock,
                return_value=([post], 1, 1),
            ):
                resp = await client.post(
                    "/api/v1/posts/search",
                    json={"keyword": "AI learning", "logic": "OR"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestGetPost:
    @pytest.mark.anyio
    async def test_get_post(self, client):
        """GET /posts/{id} → 200."""
        post_id = uuid.uuid4()
        post = _make_post(post_id=post_id)

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value=post):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["title"] == "Test Post"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_post_not_found(self, client):
        """GET /posts/{id} → 404."""
        post_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value=None):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()


class TestUpdatePost:
    @pytest.mark.anyio
    async def test_update_post(self, client):
        """PUT /posts/{id} → 200."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        post = _make_post(post_id=post_id, user_id=user_id)
        post["title"] = "Updated Title"
        post["version"] = 2

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.update_post", new_callable=AsyncMock, return_value=post),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "Updated Title", "content": "<p>Body</p>", "version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["title"] == "Updated Title"
        finally:
            _clear_overrides()


class TestPostHistory:
    @pytest.mark.anyio
    async def test_post_history(self, client):
        """GET /posts/{id}/history → 200."""
        post_id = uuid.uuid4()
        post = _make_post(post_id=post_id)
        now = datetime.now(timezone.utc).isoformat()
        history = [
            {
                "id": str(uuid.uuid4()),
                "version": 1,
                "title": "Original",
                "content": "body",
                "edited_at": now,
            },
        ]

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value=post),
                patch(f"{_EP}.get_post_history", new_callable=AsyncMock, return_value=history),
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/history",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()


class TestUpdatePostRateLimit:
    @pytest.mark.anyio
    async def test_update_post_rate_limited(self, client):
        """PUT /posts/{id} → 429 when edit rate limit exceeded."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "Updated", "content": "<p>Body</p>", "version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestSearchPostsSort:
    @pytest.mark.anyio
    async def test_search_posts_with_sort(self, client):
        """POST /posts/search with sort param → 200, sort forwarded to service."""
        post = _make_post()

        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.search_posts",
                new_callable=AsyncMock,
                return_value=([post], 1, 1),
            ) as mock_search:
                resp = await client.post(
                    "/api/v1/posts/search",
                    json={"keyword": "test", "sort": "oldest"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_search.call_args.kwargs
                assert call_kwargs.get("sort") == "oldest"
        finally:
            _clear_overrides()


class TestCreatePostFKViolation:
    @pytest.mark.anyio
    async def test_create_post_invalid_category_returns_400(self, client):
        """POST /posts with deleted category → 400."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP}.create_post",
                new_callable=AsyncMock,
                side_effect=ValueError("Category not found or has been deleted."),
            ):
                resp = await client.post(
                    "/api/v1/posts",
                    json={
                        "title": "Test",
                        "content": "<p>Body</p>",
                        "category_id": str(uuid.uuid4()),
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "Category" in resp.json()["detail"]
        finally:
            _clear_overrides()


class TestBulkDeletePosts:
    @pytest.mark.anyio
    async def test_bulk_delete_posts_admin(self, client):
        """DELETE /posts/bulk by ADMIN → 200."""
        import json as _json

        post_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        try:
            _override_auth("ADMIN")
            with (
                patch(
                    "app.services.post.bulk_soft_delete",
                    new_callable=AsyncMock,
                    return_value=2,
                ),
                patch("app.services.audit.log_action", new_callable=AsyncMock),
            ):
                resp = await client.request(
                    "DELETE",
                    "/api/v1/posts/bulk",
                    content=_json.dumps({"post_ids": post_ids}),
                    headers={
                        "Authorization": "Bearer fake",
                        "Content-Type": "application/json",
                    },
                )
                assert resp.status_code == 200
                assert resp.json()["deleted_count"] == 2
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_bulk_delete_posts_forbidden_member(self, client):
        """DELETE /posts/bulk by MEMBER → 403."""
        import json as _json

        try:
            _override_auth("MEMBER")
            resp = await client.request(
                "DELETE",
                "/api/v1/posts/bulk",
                content=_json.dumps({"post_ids": [str(uuid.uuid4())]}),
                headers={
                    "Authorization": "Bearer fake",
                    "Content-Type": "application/json",
                },
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()
