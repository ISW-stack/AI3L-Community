"""Tests for Bug #11: Empty title validation gap — whitespace-only title must be rejected."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.posts"


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user, require_role
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    # require_role returns get_current_user in the dependency chain
    app.dependency_overrides[require_role("SUPER_ADMIN", "ADMIN", "MEMBER")] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


def _make_post(post_id=None, user_id=None):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(post_id or uuid.uuid4()),
        "title": "Updated Title",
        "content": "<p>Body</p>",
        "author": {
            "id": uid,
            "username": "testuser",
            "display_name": "Test User",
            "avatar_url": None,
        },
        "category_id": None,
        "category_name": None,
        "sig_id": None,
        "sig_name": None,
        "keywords": ["test"],
        "allow_comments": True,
        "version": 2,
        "comment_count": 0,
        "view_count": 0,
        "is_pinned": False,
        "reactions": None,
        "last_comment_at": None,
        "created_at": now,
        "updated_at": now,
    }


class TestEmptyTitleValidation:
    """Tests for the empty title validation in PUT /posts/{post_id}."""

    @pytest.mark.anyio
    async def test_whitespace_only_title_rejected(self, client):
        """PUT /posts/{id} with title='   ' should return 400."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        payload, uid = _override_auth("MEMBER", user_id=user_id)
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "   ", "version": 1},
                )
                assert resp.status_code == 400
                data = resp.json()
                detail = data["detail"]
                assert detail["code"] == "SYS_422"
                assert "empty" in detail["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_valid_title_accepted(self, client):
        """PUT /posts/{id} with a valid title should succeed."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        payload, uid = _override_auth("MEMBER", user_id=user_id)
        post = _make_post(post_id=post_id, user_id=uid)
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.update_post", new_callable=AsyncMock, return_value=post),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "Valid Title", "version": 1},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_none_title_not_rejected(self, client):
        """PUT /posts/{id} with title=None (not provided) + other fields should work."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        payload, uid = _override_auth("MEMBER", user_id=user_id)
        post = _make_post(post_id=post_id, user_id=uid)
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.update_post", new_callable=AsyncMock, return_value=post),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"content": "<p>New content</p>", "version": 1},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_tabs_and_newlines_title_rejected(self, client):
        """PUT /posts/{id} with title of tabs/newlines should return 400."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        payload, uid = _override_auth("MEMBER", user_id=user_id)
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "\t\n  ", "version": 1},
                )
                assert resp.status_code == 400
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_no_fields_provided_rejected(self, client):
        """PUT /posts/{id} with no update fields should return 400."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        payload, uid = _override_auth("MEMBER", user_id=user_id)
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"version": 1},
                )
                assert resp.status_code == 400
                data = resp.json()
                detail = data["detail"]
                assert "At least one field" in detail["message"]
        finally:
            _clear_overrides()
