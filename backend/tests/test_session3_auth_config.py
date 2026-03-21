"""Tests for session-3 audit fixes: M-24, L-01, L-02, L-11, M-45, L-38."""

import ast
import inspect
import re
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# M-24: f-string logging -> %s format
# ---------------------------------------------------------------------------


class TestM24LoggingFormat:
    """M-24: Exception handlers in main.py must use %s-style logging, not f-strings."""

    def test_exception_handlers_use_percent_format(self) -> None:
        """Read main.py source and verify no f-string logging in exception handlers."""
        import app.main as main_mod

        source = inspect.getsource(main_mod)
        tree = ast.parse(source)

        # Find all function definitions that are exception handlers
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and "exception_handler" in node.name:
                func_source = ast.get_source_segment(source, node)
                if func_source is None:
                    continue
                # Check for logger.error/warning/info calls with f-strings
                # Pattern: logger.<level>(f"...") or logger.<level>(f'...')
                fstring_log = re.findall(
                    r'logger\.\w+\(\s*f["\']', func_source
                )
                assert not fstring_log, (
                    f"Exception handler '{node.name}' uses f-string logging. "
                    f"Should use %-format: logger.error('msg %s', var)"
                )

    def test_unhandled_exception_handler_exists(self) -> None:
        """Verify the unhandled_exception_handler is registered on the app."""
        from app.main import app

        # FastAPI stores exception handlers in exception_handlers dict
        assert Exception in app.exception_handlers

    def test_validation_exception_handler_no_fstring_logging(self) -> None:
        """Specifically verify the validation_exception_handler source has no f-string logs."""
        from app.main import validation_exception_handler

        source = inspect.getsource(validation_exception_handler)
        fstring_log = re.findall(r'logger\.\w+\(\s*f["\']', source)
        assert not fstring_log, (
            "validation_exception_handler uses f-string logging"
        )

    def test_unhandled_exception_handler_no_fstring_logging(self) -> None:
        """Specifically verify the unhandled_exception_handler source has no f-string logs."""
        from app.main import unhandled_exception_handler

        source = inspect.getsource(unhandled_exception_handler)
        fstring_log = re.findall(r'logger\.\w+\(\s*f["\']', source)
        assert not fstring_log, (
            "unhandled_exception_handler uses f-string logging"
        )


# ---------------------------------------------------------------------------
# L-01: Password change clears cookies
# ---------------------------------------------------------------------------

_USERS_EP = "app.api.v1.endpoints.users"


def _override_auth(role: str = "MEMBER", user_id: str | None = None):
    """Override get_current_user dependency to return a fake payload."""
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestL01PasswordChangeClearsCookies:
    """L-01: PUT /users/me/password must delete access_token cookie."""

    @pytest.mark.asyncio
    async def test_change_password_deletes_access_token_cookie(self, client) -> None:
        """After successful password change, response must clear access_token cookie."""
        try:
            payload, uid = _override_auth("MEMBER")

            with (
                patch(
                    f"{_USERS_EP}.change_password",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
                patch(
                    f"{_USERS_EP}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_USERS_EP}.revoke_user_sessions",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
                patch(
                    f"{_USERS_EP}.emit",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.put(
                    "/api/v1/users/me/password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "NewPass456!",
                    },
                )

            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

            # Check that the Set-Cookie header deletes the access_token
            set_cookie_headers = resp.headers.get_list("set-cookie")
            access_token_cookies = [
                c for c in set_cookie_headers if "access_token" in c
            ]
            assert len(access_token_cookies) > 0, (
                "Response must include Set-Cookie header for access_token deletion"
            )

            # Verify the cookie is being deleted (max-age=0 or expires in the past)
            cookie_str = access_token_cookies[0].lower()
            is_deleted = (
                'max-age=0' in cookie_str
                or '""' in cookie_str
                or "expires=thu, 01 jan 1970" in cookie_str
            )
            assert is_deleted, (
                f"access_token cookie should be deleted (max-age=0 or past expires). "
                f"Got: {access_token_cookies[0]}"
            )
        finally:
            _clear_overrides()

    @pytest.mark.asyncio
    async def test_change_password_also_deletes_csrf_cookie(self, client) -> None:
        """Both access_token and csrf_token cookies should be cleared."""
        try:
            payload, uid = _override_auth("MEMBER")

            with (
                patch(
                    f"{_USERS_EP}.change_password",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
                patch(
                    f"{_USERS_EP}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_USERS_EP}.revoke_user_sessions",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
                patch(
                    f"{_USERS_EP}.emit",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.put(
                    "/api/v1/users/me/password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "NewPass456!",
                    },
                )

            assert resp.status_code == 200

            set_cookie_headers = resp.headers.get_list("set-cookie")
            csrf_cookies = [
                c for c in set_cookie_headers if "csrf_token" in c
            ]
            assert len(csrf_cookies) > 0, (
                "Response must include Set-Cookie header for csrf_token deletion"
            )
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# L-02: Invite code entropy (16 hex chars = 64 bits)
# ---------------------------------------------------------------------------


class TestL02InviteCodeEntropy:
    """L-02: Invite codes must be 16 hex chars (64 bits of entropy)."""

    @pytest.mark.asyncio
    async def test_invite_code_is_16_hex_chars(self) -> None:
        """Generated invite code should have format INV-<16 uppercase hex chars>."""
        with patch(
            "app.services.auth.auth_repo.insert_invite_code",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.services.auth import create_invite_code

            code, expires_at = await create_invite_code(str(uuid.uuid4()))

        assert code.startswith("INV-"), f"Code should start with 'INV-', got: {code}"
        hex_part = code[4:]  # strip "INV-"
        assert len(hex_part) == 16, (
            f"Hex portion should be 16 chars (64 bits), got {len(hex_part)}: {hex_part}"
        )
        # Verify it's valid hexadecimal
        assert re.fullmatch(r"[0-9A-F]{16}", hex_part), (
            f"Hex portion should be uppercase hex, got: {hex_part}"
        )

    @pytest.mark.asyncio
    async def test_invite_code_not_8_chars(self) -> None:
        """Ensure the code is NOT 8 hex chars (the old weak entropy)."""
        with patch(
            "app.services.auth.auth_repo.insert_invite_code",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.services.auth import create_invite_code

            code, _ = await create_invite_code(str(uuid.uuid4()))

        hex_part = code[4:]
        assert len(hex_part) != 8, (
            "Invite code should NOT be 8 hex chars (old weak entropy)"
        )

    @pytest.mark.asyncio
    async def test_invite_codes_are_unique(self) -> None:
        """Multiple invite codes should not collide."""
        codes = []
        with patch(
            "app.services.auth.auth_repo.insert_invite_code",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.services.auth import create_invite_code

            for _ in range(5):
                code, _ = await create_invite_code(str(uuid.uuid4()))
                codes.append(code)

        assert len(set(codes)) == 5, "All invite codes should be unique"

    @pytest.mark.asyncio
    async def test_invite_code_expires_in_7_days(self) -> None:
        """Invite code should expire 7 days from now."""
        with patch(
            "app.services.auth.auth_repo.insert_invite_code",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.services.auth import create_invite_code

            before = datetime.now(timezone.utc)
            _, expires_at = await create_invite_code(str(uuid.uuid4()))
            after = datetime.now(timezone.utc)

        expected_min = before + timedelta(days=7)
        expected_max = after + timedelta(days=7)
        assert expected_min <= expires_at <= expected_max


# ---------------------------------------------------------------------------
# L-11: Avatar presigned URL uses 3600s expiry
# ---------------------------------------------------------------------------


class TestL11AvatarPresignedUrlExpiry:
    """L-11: resolve_avatar_url() must generate presigned URLs with 3600s expiry."""

    def test_resolve_avatar_url_calls_generate_presigned_url_with_3600(self) -> None:
        """When avatar_url is a storage key, presigned URL uses expires_in=3600."""
        from app.converters.user_converter import resolve_avatar_url

        mock_generate = MagicMock(return_value="https://example.com/signed-url")

        with patch(
            "app.core.storage.generate_presigned_url",
            mock_generate,
        ):
            result = resolve_avatar_url("avatars/user-id/abc123.jpg")

        mock_generate.assert_called_once_with(
            "avatars/user-id/abc123.jpg", expires_in=3600
        )
        assert result == "https://example.com/signed-url"

    def test_resolve_avatar_url_skips_http_urls(self) -> None:
        """URLs starting with http:// or https:// should be returned as-is."""
        from app.converters.user_converter import resolve_avatar_url

        url = "https://example.com/avatar.png"
        assert resolve_avatar_url(url) == url

    def test_resolve_avatar_url_returns_none_for_none(self) -> None:
        """None avatar_url should return None."""
        from app.converters.user_converter import resolve_avatar_url

        assert resolve_avatar_url(None) is None

    @pytest.mark.asyncio
    async def test_async_resolve_avatar_url_uses_3600(self) -> None:
        """Async version also uses 3600s expiry."""
        from app.converters.user_converter import async_resolve_avatar_url

        mock_generate = AsyncMock(return_value="https://example.com/signed-url")

        with patch(
            "app.core.async_storage.generate_presigned_url",
            mock_generate,
        ):
            result = await async_resolve_avatar_url("avatars/user-id/abc123.jpg")

        mock_generate.assert_called_once_with(
            "avatars/user-id/abc123.jpg", expires_in=3600
        )
        assert result == "https://example.com/signed-url"

    def test_generate_presigned_url_default_expiry_is_3600(self) -> None:
        """The generate_presigned_url function itself defaults to 3600s."""
        from app.core.storage import generate_presigned_url

        sig = inspect.signature(generate_presigned_url)
        assert sig.parameters["expires_in"].default == 3600


# ---------------------------------------------------------------------------
# M-45: Audit log retention Celery task
# ---------------------------------------------------------------------------


class TestM45AuditLogRetention:
    """M-45: cleanup_old_audit_logs task must exist in Celery with Beat schedule."""

    def test_cleanup_old_audit_logs_task_exists(self) -> None:
        """Task 'cleanup_old_audit_logs' should be registered in Celery."""
        # Import the cleanup module to ensure tasks are registered
        import app.tasks.cleanup  # noqa: F401
        from app.celery_app import celery

        assert "cleanup_old_audit_logs" in celery.tasks or any(
            t.endswith("cleanup_old_audit_logs") for t in celery.tasks
        ), "cleanup_old_audit_logs task not registered in Celery"

    def test_cleanup_old_audit_logs_in_beat_schedule(self) -> None:
        """Beat schedule must include the audit log cleanup task."""
        from app.celery_app import celery

        schedule = celery.conf.beat_schedule
        audit_entries = {
            name: entry
            for name, entry in schedule.items()
            if entry.get("task") == "cleanup_old_audit_logs"
        }
        assert len(audit_entries) > 0, (
            "No beat_schedule entry found for cleanup_old_audit_logs"
        )

    def test_cleanup_old_audit_logs_daily_schedule(self) -> None:
        """Audit log cleanup should run daily (86400s)."""
        from app.celery_app import celery

        for name, entry in celery.conf.beat_schedule.items():
            if entry.get("task") == "cleanup_old_audit_logs":
                assert entry["schedule"] == 86400.0, (
                    f"Expected daily schedule (86400s), got {entry['schedule']}"
                )
                break
        else:
            pytest.fail("cleanup_old_audit_logs not found in beat_schedule")

    def test_audit_repo_delete_old_logs_exists(self) -> None:
        """audit_repo.delete_old_logs() must exist and accept 'days' parameter."""
        from app.repositories import audit_repo

        assert hasattr(audit_repo, "delete_old_logs"), (
            "audit_repo missing delete_old_logs function"
        )
        sig = inspect.signature(audit_repo.delete_old_logs)
        assert "days" in sig.parameters, (
            "delete_old_logs must accept a 'days' parameter"
        )

    def test_audit_repo_delete_old_logs_default_90_days(self) -> None:
        """Default retention should be 90 days."""
        from app.repositories import audit_repo

        sig = inspect.signature(audit_repo.delete_old_logs)
        assert sig.parameters["days"].default == 90

    def test_cleanup_task_default_days_is_90(self) -> None:
        """The Celery task function should default to 90 days."""
        from app.tasks.cleanup import cleanup_old_audit_logs

        sig = inspect.signature(cleanup_old_audit_logs)
        assert sig.parameters["days"].default == 90


# ---------------------------------------------------------------------------
# L-38: Notifications cleanup Celery task
# ---------------------------------------------------------------------------


class TestL38NotificationsCleanup:
    """L-38: cleanup_old_read_notifications task must exist with Beat schedule."""

    def test_cleanup_old_read_notifications_task_exists(self) -> None:
        """Task 'cleanup_old_read_notifications' should be registered in Celery."""
        from app.celery_app import celery

        assert "cleanup_old_read_notifications" in celery.tasks or any(
            t.endswith("cleanup_old_read_notifications") for t in celery.tasks
        ), "cleanup_old_read_notifications task not registered in Celery"

    def test_cleanup_old_read_notifications_in_beat_schedule(self) -> None:
        """Beat schedule must include the notification cleanup task."""
        from app.celery_app import celery

        schedule = celery.conf.beat_schedule
        notif_entries = {
            name: entry
            for name, entry in schedule.items()
            if entry.get("task") == "cleanup_old_read_notifications"
        }
        assert len(notif_entries) > 0, (
            "No beat_schedule entry found for cleanup_old_read_notifications"
        )

    def test_notification_repo_delete_old_read_notifications_exists(self) -> None:
        """notification_repo.delete_old_read_notifications() must exist."""
        from app.repositories import notification_repo

        assert hasattr(notification_repo, "delete_old_read_notifications"), (
            "notification_repo missing delete_old_read_notifications function"
        )

    def test_notification_repo_accepts_days_parameter(self) -> None:
        """delete_old_read_notifications must accept a 'days' parameter."""
        from app.repositories import notification_repo

        sig = inspect.signature(notification_repo.delete_old_read_notifications)
        assert "days" in sig.parameters

    def test_notification_repo_default_90_days(self) -> None:
        """Default retention should be 90 days."""
        from app.repositories import notification_repo

        sig = inspect.signature(notification_repo.delete_old_read_notifications)
        assert sig.parameters["days"].default == 90

    def test_cleanup_notifications_task_default_days(self) -> None:
        """The Celery task function should default to 90 days."""
        from app.tasks.cleanup import cleanup_old_read_notifications

        sig = inspect.signature(cleanup_old_read_notifications)
        assert sig.parameters["days"].default == 90

    def test_beat_schedule_has_expires_option(self) -> None:
        """The notification cleanup Beat entry must have an 'expires' option."""
        from app.celery_app import celery

        for name, entry in celery.conf.beat_schedule.items():
            if entry.get("task") == "cleanup_old_read_notifications":
                opts = entry.get("options", {})
                assert "expires" in opts, (
                    f"Beat task '{name}' missing 'expires' option"
                )
                break
        else:
            pytest.fail("cleanup_old_read_notifications not found in beat_schedule")
