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
        """GET /posts/{id}/history → 200 for post owner."""
        post_id = uuid.uuid4()
        owner_id = str(uuid.uuid4())
        post = _make_post(post_id=post_id, user_id=owner_id)
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
            _override_auth("MEMBER", user_id=owner_id)
            with (
                patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value=post),
                patch(f"{_EP}.get_post_history", new_callable=AsyncMock, return_value=(history, 1)),
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
                assert "Category" in resp.json()["detail"]["message"]
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


class TestGetPostsList:
    @pytest.mark.anyio
    async def test_get_posts_list(self, client):
        """GET /posts → 200 with mocked list_posts."""
        post = _make_post()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={
                    "posts": [post],
                    "total": 1,
                    "total_pages": 1,
                    "next_cursor": None,
                    "has_more": None,
                },
            ):
                resp = await client.get(
                    "/api/v1/posts",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["posts"]) == 1
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_posts_list_with_filters(self, client):
        """GET /posts?category_id=xxx&sort=oldest → 200, verify params forwarded."""
        post = _make_post()
        cat_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={
                    "posts": [post],
                    "total": 1,
                    "total_pages": 1,
                    "next_cursor": None,
                    "has_more": None,
                },
            ) as mock_list:
                resp = await client.get(
                    f"/api/v1/posts?category_id={cat_id}&sort=oldest",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_list.call_args.kwargs
                assert call_kwargs.get("category_id") == cat_id
                assert call_kwargs.get("sort") == "oldest"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_posts_list_forbidden_unauthenticated(self, client):
        """GET /posts without auth → 401."""
        resp = await client.get("/api/v1/posts")
        assert resp.status_code == 401


class TestDeletePost:
    @pytest.mark.anyio
    async def test_delete_post_admin(self, client):
        """DELETE /posts/{id} by ADMIN → 204."""
        post_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.soft_delete_post", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.emit", new_callable=AsyncMock),
            ):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_post_owner(self, client):
        """DELETE /posts/{id} by MEMBER owner → 204."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(
                    f"{_EP}.soft_delete_post",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(f"{_EP}.emit", new_callable=AsyncMock),
            ):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_post_owner_emits_user_audit(self, client):
        """DELETE /posts/{id} by MEMBER → emits USER_DELETE_POST audit event."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(
                    f"{_EP}.soft_delete_post",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(f"{_EP}.emit", new_callable=AsyncMock) as mock_emit,
            ):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
                mock_emit.assert_called_once()
                call_kwargs = mock_emit.call_args
                assert call_kwargs[0][0] == "audit.action"
                assert call_kwargs[1]["action"] == "USER_DELETE_POST"
                assert call_kwargs[1]["target_id"] == str(post_id)
                assert call_kwargs[1]["user_id"] == user_id
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_post_admin_emits_admin_audit(self, client):
        """DELETE /posts/{id} by ADMIN → emits ADMIN_DELETE_POST audit event."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("ADMIN", user_id=user_id)
            with (
                patch(
                    f"{_EP}.soft_delete_post",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(f"{_EP}.emit", new_callable=AsyncMock) as mock_emit,
            ):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
                mock_emit.assert_called_once()
                call_kwargs = mock_emit.call_args
                assert call_kwargs[0][0] == "audit.action"
                assert call_kwargs[1]["action"] == "ADMIN_DELETE_POST"
                assert call_kwargs[1]["target_id"] == str(post_id)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_post_not_found(self, client):
        """DELETE /posts/{id} → 404 when soft_delete_post returns False."""
        post_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.soft_delete_post", new_callable=AsyncMock, return_value=False),
                patch(f"{_EP}.emit", new_callable=AsyncMock),
            ):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_post_forbidden_guest(self, client):
        """DELETE /posts/{id} by GUEST → 403."""
        post_id = uuid.uuid4()
        try:
            _override_auth("GUEST")
            resp = await client.delete(
                f"/api/v1/posts/{post_id}",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestTogglePin:
    @pytest.mark.anyio
    async def test_toggle_pin_admin(self, client):
        """PATCH /posts/{id}/pin → 200 with is_pinned=true."""
        post_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.pin_post",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.patch(
                    f"/api/v1/posts/{post_id}/pin",
                    json={"is_pinned": True},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["is_pinned"] is True
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_toggle_pin_not_found(self, client):
        """PATCH /posts/{id}/pin → 404 when pin_post returns False."""
        post_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.pin_post",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.patch(
                    f"/api/v1/posts/{post_id}/pin",
                    json={"is_pinned": True},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_toggle_pin_forbidden_member(self, client):
        """PATCH /posts/{id}/pin by MEMBER → 403."""
        post_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            resp = await client.patch(
                f"/api/v1/posts/{post_id}/pin",
                json={"is_pinned": True},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestGetTrending:
    @pytest.mark.anyio
    async def test_get_trending(self, client):
        """GET /posts/trending → 200."""
        posts = [_make_post(), _make_post()]
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.get_trending_posts",
                new_callable=AsyncMock,
                return_value=posts,
            ):
                resp = await client.get(
                    "/api/v1/posts/trending",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert len(resp.json()) == 2
        finally:
            _clear_overrides()


class TestUpdatePostVersionConflict:
    @pytest.mark.anyio
    async def test_update_post_version_conflict_409(self, client):
        """PUT /posts/{id} with version conflict → 409."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.update_post",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Version conflict"),
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "New Title", "content": "<p>Body</p>", "version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_post_permission_denied_403(self, client):
        """PUT /posts/{id} by non-owner → 403."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.update_post",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Not the author"),
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "New Title", "content": "<p>Body</p>", "version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_post_not_found(self, client):
        """PUT /posts/{id} → 404 when update_post returns None."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.update_post", new_callable=AsyncMock, return_value=None),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "New Title", "content": "<p>Body</p>", "version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_post_no_fields(self, client):
        """PUT /posts/{id} with empty body → 400."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "At least one field" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()


class TestPostHistoryForbiddenNonOwner:
    @pytest.mark.anyio
    async def test_post_history_forbidden_for_non_owner(self, client):
        """GET /posts/{id}/history → 403 when user is not the post owner and not admin."""
        post_id = uuid.uuid4()
        owner_id = str(uuid.uuid4())
        viewer_id = str(uuid.uuid4())
        post = _make_post(post_id=post_id, user_id=owner_id)

        try:
            _override_auth("MEMBER", user_id=viewer_id)
            with patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value=post):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/history",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "Not authorized" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_post_history_allowed_for_admin(self, client):
        """GET /posts/{id}/history → 200 for ADMIN even if not the owner."""
        post_id = uuid.uuid4()
        owner_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        post = _make_post(post_id=post_id, user_id=owner_id)
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
            _override_auth("ADMIN", user_id=admin_id)
            with (
                patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value=post),
                patch(f"{_EP}.get_post_history", new_callable=AsyncMock, return_value=(history, 1)),
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/history",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestPageParameterUpperBound:
    """Page parameter validation — le=10000 on Query(page)."""

    @pytest.mark.anyio
    async def test_page_exceeds_upper_bound_returns_422(self, client):
        """GET /posts?page=10001 → 422 validation error."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/posts?page=10001",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_at_upper_bound_accepted(self, client):
        """GET /posts?page=10000 → 200 (boundary value accepted)."""
        post = _make_post()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={
                    "posts": [post],
                    "total": 1,
                    "total_pages": 10000,
                    "next_cursor": None,
                    "has_more": None,
                },
            ):
                resp = await client.get(
                    "/api/v1/posts?page=10000",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_zero_returns_422(self, client):
        """GET /posts?page=0 → 422 validation error (ge=1)."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/posts?page=0",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_page_negative_returns_422(self, client):
        """GET /posts?page=-1 → 422 validation error."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/posts?page=-1",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


class TestPostHistoryNotFound:
    @pytest.mark.anyio
    async def test_post_history_not_found(self, client):
        """GET /posts/{id}/history → 404 when post does not exist."""
        post_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value=None):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/history",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()
