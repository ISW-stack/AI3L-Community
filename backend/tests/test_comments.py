"""Tests for comments endpoints — get, create, delete, toggle reaction."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.comments"


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


def _make_comment(post_id=None, user_id=None, comment_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(comment_id or uuid.uuid4()),
        "post_id": str(post_id or uuid.uuid4()),
        "content": "Test comment",
        "author": {
            "id": uid,
            "username": "testuser",
            "display_name": "Test User",
            "avatar_url": None,
        },
        "parent_id": None,
        "mentions": None,
        "reactions": {},
        "created_at": now,
        "updated_at": now,
    }


class TestGetComments:
    @pytest.mark.anyio
    async def test_get_comments(self, client):
        """GET /posts/{pid}/comments → 200 with comment list."""
        post_id = uuid.uuid4()
        comment = _make_comment(post_id=post_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value={"id": post_id}),
                patch(f"{_EP}.list_comments", new_callable=AsyncMock, return_value=([comment], 1)),
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/comments",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["comments"]) == 1
        finally:
            _clear_overrides()


class TestCreateComment:
    @pytest.mark.anyio
    async def test_create_comment(self, client):
        """POST /posts/{pid}/comments → 201."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        comment = _make_comment(post_id=post_id, user_id=user_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_comment", new_callable=AsyncMock, return_value=comment),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/comments",
                    json={"content": "Test comment"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["content"] == "Test comment"
        finally:
            _clear_overrides()


class TestDeleteComment:
    @pytest.mark.anyio
    async def test_delete_comment(self, client):
        """DELETE /posts/{pid}/comments/{cid} → 200."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.soft_delete_comment", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestToggleReaction:
    @pytest.mark.anyio
    async def test_toggle_reaction(self, client):
        """POST /posts/{pid}/comments/{cid}/reactions → 200."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        comment = _make_comment(post_id=post_id, comment_id=comment_id)
        comment["reactions"] = {"LIKE": [str(uuid.uuid4())]}

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.add_reaction", new_callable=AsyncMock, return_value=comment):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}/reactions",
                    json={"reaction": "LIKE"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "LIKE" in resp.json()["reactions"]
        finally:
            _clear_overrides()
