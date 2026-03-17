"""Tests for structured AppError responses across endpoints.

Verifies that all modified endpoints return structured error payloads
with {"detail": {"code": "...", "message": "..."}} instead of plain strings.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import make_user_dict

_AUTH_EP = "app.api.v1.endpoints.auth"
_FILES_EP = "app.api.v1.endpoints.files"
_FORMS_EP = "app.api.v1.endpoints.forms"
_ADMIN_EP = "app.api.v1.endpoints.admin"
_ABOUT_EP = "app.api.v1.endpoints.about"
_APPS_EP = "app.api.v1.endpoints.applications"
_INVITE_REPO = "app.repositories.invite_code_repo"


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


def _assert_structured_error(resp, expected_code: str, expected_status: int):
    """Assert response has structured error format with the given code and HTTP status."""
    assert resp.status_code == expected_status
    detail = resp.json()["detail"]
    assert isinstance(detail, dict), f"Expected dict, got {type(detail)}: {detail}"
    assert "code" in detail, f"Missing 'code' key in {detail}"
    assert "message" in detail, f"Missing 'message' key in {detail}"
    assert detail["code"] == expected_code


# ── Auth endpoint structured errors ────────────────────────────────────


class TestAuthStructuredErrors:
    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False)
    async def test_login_rate_limit_returns_sys_429(self, mock_rl, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "x",
                "password": "x",
                "captcha_id": "x",
                "captcha_code": "x",
            },
        )
        _assert_structured_error(resp, "SYS_429", 429)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.verify_captcha", new_callable=AsyncMock, return_value=False)
    async def test_login_bad_captcha_returns_auth_005(
        self, mock_captcha, mock_rl, client: AsyncClient
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "x",
                "password": "x",
                "captcha_id": "x",
                "captcha_code": "x",
            },
        )
        _assert_structured_error(resp, "AUTH_005", 400)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.authenticate_user", new_callable=AsyncMock, return_value=None)
    @patch(f"{_AUTH_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_bad_credentials_returns_auth_010(
        self, mock_captcha, mock_auth, mock_rl, client: AsyncClient
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "x",
                "password": "x",
                "captcha_id": "x",
                "captcha_code": "x",
            },
        )
        _assert_structured_error(resp, "AUTH_010", 401)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.authenticate_user", new_callable=AsyncMock)
    @patch(f"{_AUTH_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_banned_returns_auth_004(
        self, mock_captcha, mock_auth, mock_rl, client: AsyncClient
    ):
        mock_auth.return_value = make_user_dict(is_banned=True, ban_reason="spam")
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "x",
                "password": "x",
                "captcha_id": "x",
                "captcha_code": "x",
            },
        )
        _assert_structured_error(resp, "AUTH_004", 403)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False)
    async def test_register_rate_limit_returns_sys_429(self, mock_rl, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "StrongPassword1",
                "display_name": "New User",
                "invite_code": "CODE-123",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        _assert_structured_error(resp, "SYS_429", 429)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.get_invite_code", new_callable=AsyncMock)
    @patch(f"{_AUTH_EP}.user_exists_by_username", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_register_duplicate_username_returns_auth_008(
        self, mock_captcha, mock_exists, mock_invite, mock_rl, client: AsyncClient
    ):
        mock_invite.return_value = {"code": "VALID-CODE", "id": uuid.uuid4()}
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "duplicate",
                "password": "StrongPassword1!",
                "display_name": "Dup User",
                "invite_code": "VALID-CODE",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        _assert_structured_error(resp, "AUTH_008", 409)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.get_invite_code", new_callable=AsyncMock, return_value=None)
    @patch(f"{_AUTH_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_register_bad_invite_returns_auth_006(
        self, mock_captcha, mock_invite, mock_rl, client: AsyncClient
    ):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "StrongPassword1",
                "display_name": "New User",
                "invite_code": "BAD-CODE",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        _assert_structured_error(resp, "AUTH_006", 400)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.get_invite_code", new_callable=AsyncMock, return_value=None)
    async def test_verify_invite_code_not_found_returns_sys_404(
        self, mock_get, mock_rl, client: AsyncClient
    ):
        resp = await client.get("/api/v1/auth/invite-code/BAD-CODE")
        _assert_structured_error(resp, "SYS_404", 404)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False)
    async def test_captcha_rate_limit_returns_sys_429(self, mock_rl, client: AsyncClient):
        resp = await client.get("/api/v1/auth/captcha")
        _assert_structured_error(resp, "SYS_429", 429)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False)
    async def test_guest_rate_limit_returns_sys_429(self, mock_rl, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/guest/INV-123",
            json={"display_name": "V", "captcha_id": "x", "captcha_code": "x"},
        )
        _assert_structured_error(resp, "SYS_429", 429)

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.get_invite_code", new_callable=AsyncMock, return_value=None)
    async def test_guest_invalid_invite_returns_auth_006(
        self, mock_invite, mock_rl, client: AsyncClient
    ):
        resp = await client.post(
            "/api/v1/auth/guest/BAD",
            json={"display_name": "V", "captcha_id": "x", "captcha_code": "x"},
        )
        _assert_structured_error(resp, "AUTH_006", 404)

    @patch(
        f"{_INVITE_REPO}.count_active_by_user",
        new_callable=AsyncMock,
        return_value=5,
    )
    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    async def test_invite_max_active_returns_sys_429(
        self, mock_rl, mock_count, client: AsyncClient
    ):
        try:
            _override_auth("MEMBER")
            resp = await client.post(
                "/api/v1/auth/invite-code",
                headers={"Authorization": "Bearer fake"},
            )
            _assert_structured_error(resp, "SYS_429", 429)
        finally:
            _clear_overrides()


# ── Auth cookie setting without type:ignore ────────────────────────────


class TestAuthCookiesNoTypeIgnore:
    """Verify cookie setting works correctly after removing type:ignore."""

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.has_consent", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.create_session", new_callable=AsyncMock, return_value=("tok", "jti-se", 3600))
    @patch(f"{_AUTH_EP}.authenticate_user", new_callable=AsyncMock)
    @patch(f"{_AUTH_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    async def test_login_sets_cookies_correctly(
        self, mock_captcha, mock_auth, mock_session, mock_consent, mock_rl, client: AsyncClient
    ):
        """Login should still set access_token and csrf_token cookies."""
        mock_auth.return_value = make_user_dict(username="alice", role="MEMBER")
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "Password1",
                "captcha_id": "cap-1",
                "captcha_code": "ABCD",
            },
        )
        assert resp.status_code == 200
        cookies = {c.name: c for c in resp.cookies.jar}
        assert "access_token" in cookies
        assert "csrf_token" in cookies

    @patch(f"{_AUTH_EP}.destroy_session", new_callable=AsyncMock)
    async def test_logout_clears_cookies_correctly(self, mock_destroy, client: AsyncClient):
        """Logout should clear cookies without error."""
        try:
            _override_auth("MEMBER")
            resp = await client.post(
                "/api/v1/auth/logout", headers={"Authorization": "Bearer fake"}
            )
            assert resp.status_code == 200
        finally:
            _clear_overrides()


# ── Admin endpoint structured errors ───────────────────────────────────


class TestAdminStructuredErrors:
    @pytest.mark.anyio
    async def test_revoke_not_found_returns_sys_404(self, client):
        code_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_INVITE_REPO}.revoke",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.patch(
                    f"/api/v1/admin/invite-codes/{code_id}/revoke",
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_404", 404)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_not_found_returns_sys_404(self, client):
        code_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_INVITE_REPO}.delete",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.delete(
                    f"/api/v1/admin/invite-codes/{code_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_404", 404)
        finally:
            _clear_overrides()


# ── About endpoint structured errors ───────────────────────────────────


class TestAboutStructuredErrors:
    @pytest.mark.anyio
    async def test_create_duplicate_returns_sys_409(self, client):
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                "app.services.contributor.github_username_exists",
                new_callable=AsyncMock,
                return_value=True,
            ):
                resp = await client.post(
                    "/api/v1/about/admin/contributors",
                    json={
                        "github_username": "dup",
                        "display_name": "Dup",
                        "role": "Contributor",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_409", 409)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_not_found_returns_sys_404(self, client):
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                "app.services.contributor.update_contributor",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.put(
                    f"/api/v1/about/admin/contributors/{uuid.uuid4()}",
                    json={"display_name": "X"},
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_404", 404)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_not_found_returns_sys_404(self, client):
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                "app.services.contributor.delete_contributor",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.request(
                    "DELETE",
                    f"/api/v1/about/admin/contributors/{uuid.uuid4()}",
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_404", 404)
        finally:
            _clear_overrides()


# ── Applications endpoint structured errors ────────────────────────────


class TestApplicationsStructuredErrors:
    @pytest.mark.anyio
    async def test_apply_non_guest_returns_sys_422(self, client):
        try:
            _override_auth("MEMBER")
            resp = await client.post(
                "/api/v1/users/apply-member",
                json={"description": "Want to join"},
                headers={"Authorization": "Bearer fake"},
            )
            _assert_structured_error(resp, "SYS_422", 400)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_apply_duplicate_returns_sys_409(self, client):
        try:
            _override_auth("GUEST")
            with patch(
                f"{_APPS_EP}.create_application",
                new_callable=AsyncMock,
                side_effect=ValueError("pending"),
            ):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json={"description": "I'd like to join"},
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_409", 409)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_review_not_found_returns_sys_404(self, client):
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_APPS_EP}.review_application",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.put(
                    f"/api/v1/admin/applications/{uuid.uuid4()}/review",
                    json={"action": "APPROVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_404", 404)
        finally:
            _clear_overrides()


# ── File validation structured errors ──────────────────────────────────


class TestFileValidationStructuredErrors:
    def test_validate_avatar_bad_type_returns_file_001(self):
        from app.core.errors import AppError
        from app.core.file_validation import validate_avatar

        with pytest.raises(AppError) as exc_info:
            validate_avatar("application/pdf", b"\x00" * 100)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "FILE_001"

    def test_validate_avatar_too_large_returns_file_001(self):
        from app.core.errors import AppError
        from app.core.file_validation import validate_avatar

        # 3 MB exceeds the 2 MB limit
        data = b"\xff\xd8\xff" + b"\x00" * (3 * 1024 * 1024)
        with pytest.raises(AppError) as exc_info:
            validate_avatar("image/jpeg", data)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "FILE_001"

    def test_validate_avatar_bad_magic_returns_file_001(self):
        from app.core.errors import AppError
        from app.core.file_validation import validate_avatar

        # Valid type, valid size, but wrong magic bytes
        data = b"\x00\x00\x00\x00" + b"\x00" * 100
        with pytest.raises(AppError) as exc_info:
            validate_avatar("image/png", data)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "FILE_001"

    def test_validate_editor_file_bad_extension_returns_file_001(self):
        from app.core.errors import AppError
        from app.core.file_validation import validate_editor_file

        with pytest.raises(AppError) as exc_info:
            validate_editor_file("evil.exe", b"\x00" * 100)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "FILE_001"
        assert "not allowed" in exc_info.value.detail["message"].lower()

    def test_validate_editor_file_too_large_returns_file_001(self):
        from app.core.errors import AppError
        from app.core.file_validation import validate_editor_file

        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * (21 * 1024 * 1024)
        with pytest.raises(AppError) as exc_info:
            validate_editor_file("test.png", data)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "FILE_001"

    def test_validate_editor_file_bad_magic_returns_file_001(self):
        from app.core.errors import AppError
        from app.core.file_validation import validate_editor_file

        data = b"\x00\x00\x00\x00" + b"\x00" * 100
        with pytest.raises(AppError) as exc_info:
            validate_editor_file("test.png", data)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "FILE_001"
        assert "magic number" in exc_info.value.detail["message"].lower()


# ── Forms endpoint structured errors ───────────────────────────────────


class TestFormsStructuredErrors:
    @pytest.mark.anyio
    async def test_get_form_not_found_returns_sys_404(self, client):
        form_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_FORMS_EP}.get_form_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_404", 404)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_submit_rate_limit_returns_sys_429(self, client):
        form_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_FORMS_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "x"}},
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_429", 429)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_submit_already_submitted_returns_sys_409(self, client):
        form_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_FORMS_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_FORMS_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Already submitted a response"),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "x"}},
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_409", 409)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_submit_validation_error_returns_sys_422(self, client):
        form_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_FORMS_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_FORMS_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Missing required field q1"),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {}},
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_422", 400)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_export_rate_limit_returns_sys_429(self, client):
        form_id = uuid.uuid4()
        sig_id = str(uuid.uuid4())
        try:
            _override_auth("ADMIN")
            form = {
                "id": str(form_id),
                "sig_id": sig_id,
                "created_by": "x",
            }
            with (
                patch(
                    f"{_FORMS_EP}.get_form_by_id",
                    new_callable=AsyncMock,
                    return_value=form,
                ),
                patch(f"{_FORMS_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_FORMS_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/export",
                    headers={"Authorization": "Bearer fake"},
                )
                _assert_structured_error(resp, "SYS_429", 429)
        finally:
            _clear_overrides()


# ── Files endpoint structured errors ───────────────────────────────────


class TestFilesStructuredErrors:
    @patch(
        "app.core.deps.get_user_by_id", new_callable=AsyncMock, return_value={"is_banned": False}
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_upload_rate_limit_returns_sys_429(
        self, mock_session, mock_user, client: AsyncClient, auth_headers
    ):
        headers, user_id, _ = auth_headers("MEMBER")
        with patch(
            f"{_FILES_EP}.check_rate_limit",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = await client.post(
                "/api/v1/files/upload/editor",
                headers=headers,
                files={"file": ("test.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
            )
            _assert_structured_error(resp, "SYS_429", 429)

    @patch(
        "app.core.deps.get_user_by_id", new_callable=AsyncMock, return_value={"is_banned": False}
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_serve_file_invalid_key_returns_sys_422(
        self, mock_session, mock_user, client: AsyncClient, auth_headers
    ):
        headers, user_id, _ = auth_headers("ADMIN")
        resp = await client.get(
            "/api/v1/files/content/..%2F..%2Fetc%2Fpasswd",
            headers=headers,
        )
        _assert_structured_error(resp, "SYS_422", 400)

    @patch(
        "app.core.deps.get_user_by_id", new_callable=AsyncMock, return_value={"is_banned": False}
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_presigned_invalid_key_returns_sys_422(
        self, mock_session, mock_user, client: AsyncClient, auth_headers
    ):
        headers, user_id, _ = auth_headers("ADMIN")
        resp = await client.get(
            "/api/v1/files/presigned/..%2F..%2Fetc%2Fpasswd",
            headers=headers,
        )
        _assert_structured_error(resp, "SYS_422", 400)

    @patch(
        "app.core.deps.get_user_by_id", new_callable=AsyncMock, return_value={"is_banned": False}
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_scan_status_invalid_key_returns_sys_422(
        self, mock_session, mock_user, client: AsyncClient, auth_headers
    ):
        headers, user_id, _ = auth_headers("MEMBER")
        resp = await client.get(
            "/api/v1/files/scan-status/..%2F..%2Fetc%2Fpasswd",
            headers=headers,
        )
        _assert_structured_error(resp, "SYS_422", 400)

    @patch(
        "app.core.deps.get_user_by_id", new_callable=AsyncMock, return_value={"is_banned": False}
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_delete_file_not_found_returns_sys_404(
        self, mock_session, mock_user, client: AsyncClient, auth_headers
    ):
        headers, user_id, _ = auth_headers("ADMIN")
        with patch(
            f"{_FILES_EP}.async_get_file_size",
            new_callable=AsyncMock,
            return_value=0,
        ):
            resp = await client.delete(
                f"/api/v1/files/content/editor/{user_id}/test.png",
                headers=headers,
            )
            _assert_structured_error(resp, "SYS_404", 404)

    @patch(
        "app.core.deps.get_user_by_id", new_callable=AsyncMock, return_value={"is_banned": False}
    )
    @patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
    async def test_delete_file_forbidden_returns_sys_403(
        self, mock_session, mock_user, client: AsyncClient, auth_headers
    ):
        headers, user_id, _ = auth_headers("MEMBER")
        other_user = str(uuid.uuid4())
        resp = await client.delete(
            f"/api/v1/files/content/editor/{other_user}/test.png",
            headers=headers,
        )
        _assert_structured_error(resp, "SYS_403", 403)
