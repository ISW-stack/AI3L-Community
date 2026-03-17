"""Tests for C10/C12/C9 — AppError standardization, type:ignore fixes, async converters.

Verifies:
1. Endpoints return {"detail": {"code": "...", "message": "..."}} format
2. Specific error codes (429 -> SYS_429, 404 -> SYS_404, etc.)
3. UserResponse includes preferences field
4. require_role uses AppError for 403
5. require_sig_admin uses AppError for 403
6. Async converter calls in users.py
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_user_dict

_EP_POSTS = "app.api.v1.endpoints.posts"
_EP_USERS = "app.api.v1.endpoints.users"
_EP_SIGS = "app.api.v1.endpoints.sigs"
_EP_NOTIF = "app.api.v1.endpoints.notifications"
_EP_COMMENTS = "app.api.v1.endpoints.comments"
_EP_CATEGORIES = "app.api.v1.endpoints.categories"
_EP_REPORTS = "app.api.v1.endpoints.reports"
_EP_PREFS = "app.api.v1.endpoints.preferences"


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


# ── Part 1: AppError format verification ──────────────────────────────


class TestAppErrorFormat:
    """Verify all error responses use {"code": "...", "message": "..."} format."""

    @pytest.mark.anyio
    async def test_post_not_found_returns_app_error_format(self, client):
        """GET /posts/{id} -> 404 with structured error."""
        post_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP_POSTS}.get_post_by_id", new_callable=AsyncMock, return_value=None):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                detail = resp.json()["detail"]
                assert isinstance(detail, dict)
                assert detail["code"] == "SYS_404"
                assert "not found" in detail["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_post_reaction_rate_limit_returns_429_code(self, client):
        """POST /posts/{id}/reactions -> 429 with SYS_429 code."""
        post_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP_POSTS}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/reactions",
                    json={"reaction": "LIKE"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_429"
                assert "too many" in detail["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_post_update_403_returns_app_error_format(self, client):
        """PUT /posts/{id} -> 403 with SYS_403 code on PermissionError."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP_POSTS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP_POSTS}.update_post",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Not the author"),
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "New", "content": "<p>Body</p>", "version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_403"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_post_update_409_returns_app_error_format(self, client):
        """PUT /posts/{id} -> 409 with SYS_409 code on version conflict."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP_POSTS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP_POSTS}.update_post",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Version conflict"),
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"title": "New", "content": "<p>Body</p>", "version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_409"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_post_update_400_validation_returns_sys_422_code(self, client):
        """PUT /posts/{id} with no fields -> 400 with SYS_422 code."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP_POSTS}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}",
                    json={"version": 1},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_422"
                assert "at least one field" in detail["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_post_rate_limit_returns_sys_429(self, client):
        """POST /posts with RateLimitError -> 429 with SYS_429 code."""
        from app.core.errors import RateLimitError

        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP_POSTS}.create_post",
                new_callable=AsyncMock,
                side_effect=RateLimitError("Rate limit exceeded"),
            ):
                resp = await client.post(
                    "/api/v1/posts",
                    json={"title": "Test", "content": "<p>Body</p>"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_429"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_post_permission_error_returns_sys_403(self, client):
        """POST /posts with PermissionError -> 403 with SYS_403 code."""
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP_POSTS}.create_post",
                new_callable=AsyncMock,
                side_effect=PermissionError("Not a SIG member"),
            ):
                resp = await client.post(
                    "/api/v1/posts",
                    json={"title": "Test", "content": "<p>Body</p>"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_403"
        finally:
            _clear_overrides()


class TestAppErrorFormatSigs:
    """SIG endpoints return structured AppError responses."""

    @pytest.mark.anyio
    async def test_sig_not_found_returns_sys_404(self, client):
        """GET /sigs/{id} -> 404 with SYS_404 code."""
        sig_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP_SIGS}.get_sig_by_id", new_callable=AsyncMock, return_value=None):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_404"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sig_create_duplicate_returns_sys_409(self, client):
        """POST /sigs with duplicate name -> 409 with SYS_409 code."""
        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP_SIGS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP_SIGS}.create_sig",
                    new_callable=AsyncMock,
                    side_effect=ValueError("SIG name already exists"),
                ),
            ):
                resp = await client.post(
                    "/api/v1/sigs",
                    json={"name": "Dup SIG", "description": "Desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_409"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sig_create_rate_limited_returns_sys_429(self, client):
        """POST /sigs -> 429 with SYS_429 code when rate limited."""
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP_SIGS}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    "/api/v1/sigs",
                    json={"name": "New SIG", "description": "Desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_429"
        finally:
            _clear_overrides()


class TestAppErrorFormatUsers:
    """User endpoints return structured AppError responses."""

    @pytest.mark.anyio
    async def test_user_not_found_returns_sys_404(self, client):
        """GET /users/me -> 404 with SYS_404 code when user not found."""
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(f"{_EP_USERS}.get_user_by_id", new_callable=AsyncMock, return_value=None):
                resp = await client.get(
                    "/api/v1/users/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_404"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_create_duplicate_returns_sys_409(self, client):
        """POST /users/admin/create-account with existing username -> 409 with SYS_409."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_EP_USERS}.user_exists_by_username",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.post(
                    "/api/v1/users/admin/create-account",
                    json={
                        "username": "existing",
                        "password": "StrongPass1!",
                        "display_name": "User",
                        "role": "MEMBER",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_409"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_account_sole_admin_returns_sys_409(self, client):
        """DELETE /users/me -> 409 with SYS_409 code when user is sole admin."""
        user_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER", user_id=user_id)
            with patch(
                f"{_EP_USERS}.check_sole_admin_sigs",
                new_callable=AsyncMock,
                return_value=[{"id": uuid.uuid4(), "name": "Test SIG"}],
            ):
                resp = await client.delete(
                    "/api/v1/users/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_409"
                assert "sole admin" in detail["message"].lower()
        finally:
            _clear_overrides()


class TestAppErrorFormatCategories:
    """Category endpoints return structured AppError responses."""

    @pytest.mark.anyio
    async def test_category_not_found_returns_sys_404(self, client):
        """GET /categories/{id} -> 404 with SYS_404 code."""
        cat_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_CATEGORIES}.get_category_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.get(
                    f"/api/v1/categories/{cat_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_404"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_category_duplicate_returns_sys_409(self, client):
        """POST /categories with duplicate name -> 409 with SYS_409 code."""
        import asyncpg

        try:
            _override_auth("ADMIN")
            with (
                patch(
                    f"{_EP_CATEGORIES}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_EP_CATEGORIES}.create_category",
                    new_callable=AsyncMock,
                    side_effect=asyncpg.UniqueViolationError(),
                ),
            ):
                resp = await client.post(
                    "/api/v1/categories",
                    json={"name": "Dup Cat"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_409"
        finally:
            _clear_overrides()


class TestAppErrorFormatNotifications:
    """Notification endpoints return structured AppError responses."""

    @pytest.mark.anyio
    async def test_notification_not_found_returns_sys_404(self, client):
        """PUT /notifications/{id}/read -> 404 with SYS_404 code."""
        notif_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP_NOTIF}.mark_as_read", new_callable=AsyncMock, return_value=False):
                resp = await client.put(
                    f"/api/v1/notifications/{notif_id}/read",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_404"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_notification_rate_limit_returns_sys_429(self, client):
        """GET /notifications -> 429 with SYS_429 code when rate limited."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP_NOTIF}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.get(
                    "/api/v1/notifications",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_429"
        finally:
            _clear_overrides()


class TestAppErrorFormatComments:
    """Comment endpoints return structured AppError responses."""

    @pytest.mark.anyio
    async def test_comment_empty_content_returns_sys_422(self, client):
        """POST /posts/{pid}/comments with empty content -> 400 with SYS_422 code."""
        post_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP_COMMENTS}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(f"{_EP_COMMENTS}.sanitize_html", return_value=""),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/comments",
                    json={"content": "<script>alert(1)</script>"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_422"
                assert "empty" in detail["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_comment_not_found_delete_returns_sys_404(self, client):
        """DELETE /posts/{pid}/comments/{cid} -> 404 with SYS_404 code."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_COMMENTS}.soft_delete_comment",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_404"
        finally:
            _clear_overrides()


class TestAppErrorFormatReports:
    """Report endpoints return structured AppError responses."""

    @pytest.mark.anyio
    async def test_report_post_not_found_returns_sys_404(self, client):
        """POST /posts/{pid}/report -> 404 with SYS_404 code."""
        post_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP_REPORTS}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_EP_REPORTS}.get_post_by_id",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/report",
                    json={"reason": "Spam"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_404"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_report_duplicate_returns_sys_409(self, client):
        """POST /posts/{pid}/report duplicate -> 409 with SYS_409 code."""
        post_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP_REPORTS}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_EP_REPORTS}.get_post_by_id",
                    new_callable=AsyncMock,
                    return_value={"id": post_id},
                ),
                patch(
                    f"{_EP_REPORTS}.create_report",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Already reported"),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/report",
                    json={"reason": "Spam"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_409"
        finally:
            _clear_overrides()


# ── Part 2: require_role uses AppError ──────────────────────────────


class TestRequireRoleAppError:
    """require_role dependency now returns structured AppError for 403."""

    @pytest.mark.anyio
    async def test_require_role_guest_403_returns_app_error(self, client):
        """DELETE /posts/{id} by GUEST -> 403 with SYS_403 code."""
        post_id = uuid.uuid4()
        try:
            _override_auth("GUEST")
            resp = await client.delete(
                f"/api/v1/posts/{post_id}",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
            detail = resp.json()["detail"]
            assert isinstance(detail, dict)
            assert detail["code"] == "SYS_403"
            assert "insufficient" in detail["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_require_role_member_admin_only_403(self, client):
        """PUT /users/bulk-role by ADMIN (needs SUPER_ADMIN) -> 403 with SYS_403."""
        try:
            _override_auth("ADMIN")
            resp = await client.put(
                "/api/v1/users/bulk-role",
                json={"user_ids": [str(uuid.uuid4())], "role": "MEMBER"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
            detail = resp.json()["detail"]
            assert detail["code"] == "SYS_403"
        finally:
            _clear_overrides()


# ── Part 3: UserResponse preferences field ──────────────────────────


class TestUserResponsePreferences:
    """UserResponse schema includes preferences field."""

    def test_user_response_has_preferences_field(self):
        """UserResponse must have optional preferences field."""
        from app.schemas.user import UserResponse

        fields = UserResponse.model_fields
        assert "preferences" in fields
        # Can be None
        resp = UserResponse(
            id="test-id",
            username="test",
            display_name="Test",
            role="MEMBER",
            preferences=None,
        )
        assert resp.preferences is None

    def test_user_response_preferences_with_data(self):
        """UserResponse accepts a dict for preferences."""
        from app.schemas.user import UserResponse

        prefs = {"theme": "dark", "notify_mentions": True}
        resp = UserResponse(
            id="test-id",
            username="test",
            display_name="Test",
            role="MEMBER",
            preferences=prefs,
        )
        assert resp.preferences == prefs


# ── Part 4: Async converter usage in users.py ──────────────────────


class TestAsyncConverterUsage:
    """users.py uses async converter functions instead of sync."""

    @pytest.mark.anyio
    async def test_get_profile_uses_async_converter(self, client):
        """GET /users/me calls async_user_to_response, not user_to_response."""
        user_id = str(uuid.uuid4())
        user = make_user_dict(user_id=user_id, username="alice")
        default_prefs = {"theme": "light"}

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP_USERS}.get_user_by_id", new_callable=AsyncMock, return_value=user),
                patch(
                    f"{_EP_USERS}.async_user_to_response",
                    new_callable=AsyncMock,
                ) as mock_converter,
                patch(
                    "app.services.preferences.get_user_preferences",
                    new_callable=AsyncMock,
                    return_value=default_prefs,
                ),
            ):
                from app.schemas.user import UserResponse

                mock_converter.return_value = UserResponse(
                    id=str(user["id"]),
                    username=user["username"],
                    display_name=user["display_name"],
                    role=user["role"],
                )
                resp = await client.get(
                    "/api/v1/users/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_converter.assert_awaited_once()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_public_profile_uses_async_converter(self, client):
        """GET /users/{id} calls async_user_to_public_response."""
        user_id = str(uuid.uuid4())
        user = make_user_dict(user_id=user_id, username="bob")

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP_USERS}.get_user_by_id", new_callable=AsyncMock, return_value=user),
                patch(
                    f"{_EP_USERS}.async_user_to_public_response",
                    new_callable=AsyncMock,
                ) as mock_converter,
            ):
                from app.schemas.user import PublicUserResponse

                mock_converter.return_value = PublicUserResponse(
                    id=str(user["id"]),
                    username=user["username"],
                    display_name=user["display_name"],
                    role=user["role"],
                    created_at=user["created_at"].isoformat(),
                )
                resp = await client.get(
                    f"/api/v1/users/{user_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_converter.assert_awaited_once()
        finally:
            _clear_overrides()


# ── Part 5: type:ignore fix verification ──────────────────────────


class TestTypeIgnoreFixed:
    """Verify type:ignore comments have been removed (code is type-safe)."""

    def test_no_type_ignore_in_posts_endpoint(self):
        """posts.py should have no type:ignore comments."""
        import inspect

        from app.api.v1.endpoints import posts

        source = inspect.getsource(posts)
        assert "type: ignore" not in source

    def test_no_type_ignore_in_sigs_endpoint(self):
        """sigs.py should have no type:ignore comments."""
        import inspect

        from app.api.v1.endpoints import sigs

        source = inspect.getsource(sigs)
        assert "type: ignore" not in source

    def test_no_type_ignore_in_users_endpoint(self):
        """users.py should have no type:ignore comments."""
        import inspect

        from app.api.v1.endpoints import users

        source = inspect.getsource(users)
        assert "type: ignore" not in source

    def test_no_type_ignore_in_event_bus(self):
        """event_bus.py should have no type:ignore comments."""
        import inspect

        from app.core import event_bus

        source = inspect.getsource(event_bus)
        assert "type: ignore" not in source

    def test_no_type_ignore_in_rate_limit(self):
        """rate_limit.py should have no type:ignore comments."""
        import inspect

        from app.core import rate_limit

        source = inspect.getsource(rate_limit)
        assert "type: ignore" not in source

    def test_no_type_ignore_in_event_retry(self):
        """event_retry.py should have no type:ignore comments."""
        import inspect

        from app.tasks import event_retry

        source = inspect.getsource(event_retry)
        assert "type: ignore" not in source


# ── Part 6: Preferences rate limit ──────────────────────────────


class TestPreferencesAppError:
    """Preferences endpoint returns structured AppError."""

    @pytest.mark.anyio
    async def test_preferences_rate_limited_returns_sys_429(self, client):
        """PUT /users/me/preferences -> 429 with SYS_429 code."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP_PREFS}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.put(
                    "/api/v1/users/me/preferences",
                    json={"theme": "dark"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
                detail = resp.json()["detail"]
                assert detail["code"] == "SYS_429"
        finally:
            _clear_overrides()
