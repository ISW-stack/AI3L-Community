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
            with patch(f"{_EP}.update_post", new_callable=AsyncMock, return_value=post):
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
            {"id": str(uuid.uuid4()), "version": 1, "title": "Original", "content": "body", "edited_at": now},
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
