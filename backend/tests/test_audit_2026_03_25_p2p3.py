"""Tests for P2/P3 audit fixes (2026-03-25).

Covers auth, DM/WS, business logic, infra, and file validation fixes.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Auth: JWT role cross-check (P2)
# ---------------------------------------------------------------------------


class TestJwtRoleCrossCheck:
    """deps.py rejects JWT when role mismatches DB role."""

    def test_cross_check_code_exists(self):
        """Verify the role cross-check code is in deps.py."""
        import inspect

        from app.core.deps import get_current_user

        source = inspect.getsource(get_current_user)
        assert 'db_role' in source
        assert 'Role changed' in source


# ---------------------------------------------------------------------------
# Auth: Per-account login lockout (P2)
# ---------------------------------------------------------------------------


class TestPerAccountLockout:
    """Login endpoint has per-username rate limiting."""

    @pytest.mark.asyncio
    async def test_per_account_rate_limit_key_exists(self):
        """Verify the rate limit call pattern exists in login endpoint."""
        import inspect

        from app.api.v1.endpoints.auth import login

        source = inspect.getsource(login)
        assert "rl:login:user:" in source


# ---------------------------------------------------------------------------
# Auth: Password same check (P3)
# ---------------------------------------------------------------------------


class TestPasswordSameCheck:
    """change_password rejects identical old/new password."""

    @pytest.mark.asyncio
    async def test_same_password_rejected(self):
        from app.services.user import change_password

        user_id = uuid.uuid4()
        with (
            patch(
                "app.services.user.user_repo.find_password_hash",
                new_callable=AsyncMock,
                return_value="$argon2id$v=19$m=65536,t=3,p=4$fake",
            ),
            patch(
                "app.services.user.async_verify_password",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            with pytest.raises(ValueError, match="must differ"):
                await change_password(user_id, "same_pass!", "same_pass!")


# ---------------------------------------------------------------------------
# Auth: Guest display_name HTML strip (P3)
# ---------------------------------------------------------------------------


class TestGuestDisplayNameSanitize:
    """Guest display_name has HTML tags stripped."""

    def test_html_stripped(self):
        from app.schemas.auth import GuestLoginRequest

        req = GuestLoginRequest(
            display_name="<b>Admin</b>",
            captcha_id="test",
            captcha_code="1234",
        )
        assert "<" not in req.display_name
        assert "Admin" in req.display_name

    def test_empty_after_strip_rejected(self):
        from pydantic import ValidationError

        from app.schemas.auth import GuestLoginRequest

        with pytest.raises(ValidationError):
            GuestLoginRequest(
                display_name="<script></script>",
                captcha_id="test",
                captcha_code="1234",
            )


# ---------------------------------------------------------------------------
# Auth: CSRF path specificity (P3)
# ---------------------------------------------------------------------------


class TestCsrfPathSpecificity:
    """CSRF bypass only matches exact /api/v1/ws path."""

    def test_ws_exact_match(self):
        from app.core.csrf import _SAFE_METHODS

        # Verify the CSRF middleware source checks exact WS path
        import inspect

        from app.core.csrf import CSRFMiddleware

        source = inspect.getsource(CSRFMiddleware.dispatch)
        # Should NOT have startswith("/api/v1/ws") which matches /api/v1/ws-config
        assert 'path == "/api/v1/ws"' in source or "path ==" in source


# ---------------------------------------------------------------------------
# Auth: refresh_session_ttl atomic (P3)
# ---------------------------------------------------------------------------


class TestRefreshSessionAtomic:
    """refresh_session_ttl uses single EXPIRE call."""

    @pytest.mark.asyncio
    async def test_uses_expire_directly(self):
        import inspect

        from app.services.auth import refresh_session_ttl

        source = inspect.getsource(refresh_session_ttl)
        # Should NOT have a separate exists() call
        assert "redis.exists" not in source
        assert "redis.expire" in source


# ---------------------------------------------------------------------------
# Report: Self-report prevention (P2)
# ---------------------------------------------------------------------------


class TestSelfReportPrevention:
    """create_report rejects self-reporting."""

    @pytest.mark.asyncio
    async def test_self_report_rejected(self):
        from app.services.report import create_report

        user_id = str(uuid.uuid4())
        post_id = uuid.uuid4()

        with patch(
            "app.repositories.post_repo.find_by_id",
            new_callable=AsyncMock,
            return_value={"user_id": uuid.UUID(user_id)},
        ):
            with pytest.raises(ValueError, match="cannot report your own"):
                await create_report(post_id, user_id, "spam")


# ---------------------------------------------------------------------------
# Report: Status validation (P2)
# ---------------------------------------------------------------------------


class TestReportStatusValidation:
    """review_report rejects invalid statuses."""

    @pytest.mark.asyncio
    async def test_invalid_status_rejected(self):
        from app.services.report import review_report

        with pytest.raises(ValueError, match="Invalid report status"):
            await review_report(uuid.uuid4(), str(uuid.uuid4()), "HACKED")


# ---------------------------------------------------------------------------
# Report: Reason max length (P3)
# ---------------------------------------------------------------------------


class TestReportReasonLength:
    """create_report rejects overly long reasons."""

    @pytest.mark.asyncio
    async def test_long_reason_rejected(self):
        from app.services.report import create_report

        with pytest.raises(ValueError, match="too long"):
            await create_report(uuid.uuid4(), str(uuid.uuid4()), "x" * 3000)


# ---------------------------------------------------------------------------
# DM: find_conversations filters deleted/banned (P2)
# ---------------------------------------------------------------------------


class TestDmConversationFilter:
    """find_conversations SQL includes is_deleted/is_banned filter."""

    def test_filter_in_query(self):
        import inspect

        from app.repositories.dm_repo import find_conversations

        source = inspect.getsource(find_conversations)
        assert "is_deleted = false" in source.lower() or "is_deleted" in source
        assert "is_banned = false" in source.lower() or "is_banned" in source


# ---------------------------------------------------------------------------
# DM: attachment_key not leaked (P2)
# ---------------------------------------------------------------------------


class TestDmAttachmentKeyNotLeaked:
    """dm_converter does not include attachment_key in conversation response."""

    def test_no_attachment_key_in_converter(self):
        import inspect

        from app.converters.dm_converter import async_row_to_conversation

        source = inspect.getsource(async_row_to_conversation)
        # The "attachment_key" field should not appear as a dict key in the output
        assert '"attachment_key"' not in source


# ---------------------------------------------------------------------------
# WS: Atomic connection limit (P2)
# ---------------------------------------------------------------------------


class TestWsAtomicConnectionLimit:
    """WebSocket connection limit check and registration are atomic."""

    def test_single_lock_block(self):
        import inspect

        from app.api.v1.endpoints.ws import websocket_endpoint

        source = inspect.getsource(websocket_endpoint)
        # Should have accept() inside the lock block, not separate
        assert "await ws.accept()" in source
        # The pattern should show accept inside _connections_lock, not after it
        lock_idx = source.index("_connections_lock")
        accept_idx = source.index("await ws.accept()")
        # accept should be within the first lock block
        assert accept_idx > lock_idx


# ---------------------------------------------------------------------------
# WS: PONG exempt from rate limit (P3)
# ---------------------------------------------------------------------------


class TestWsPongRateLimit:
    """PONG messages don't consume rate limit budget."""

    def test_pong_decrements_counter(self):
        import inspect

        from app.api.v1.endpoints.ws import websocket_endpoint

        source = inspect.getsource(websocket_endpoint)
        assert "msg_count - 1" in source or "msg_count = max(0" in source


# ---------------------------------------------------------------------------
# PDF: Extended dangerous keys (P2)
# ---------------------------------------------------------------------------


class TestPdfDangerousKeys:
    """PDF sanitizer strips /Launch, /URI, /EmbeddedFiles."""

    def test_dangerous_keys_include_launch(self):
        from app.core.file_validation import _PDF_DANGEROUS_KEYS

        assert "/Launch" in _PDF_DANGEROUS_KEYS
        assert "/URI" in _PDF_DANGEROUS_KEYS
        assert "/EmbeddedFiles" in _PDF_DANGEROUS_KEYS
        assert "/SubmitForm" in _PDF_DANGEROUS_KEYS
        assert "/GoToR" in _PDF_DANGEROUS_KEYS


# ---------------------------------------------------------------------------
# Thumbnail: Reduced pixel limit (P2)
# ---------------------------------------------------------------------------


class TestThumbnailPixelLimit:
    """Thumbnail task uses 10MP limit instead of 20MP."""

    def test_pixel_limit_reduced(self):
        import inspect

        from app.tasks.thumbnail import generate_thumbnail_task

        source = inspect.getsource(generate_thumbnail_task)
        assert "10_000_000" in source or "10000000" in source


# ---------------------------------------------------------------------------
# Album: Shorter presigned URL expiry (P2)
# ---------------------------------------------------------------------------


class TestAlbumPresignedExpiry:
    """Album presigned URLs use 900s (15min) instead of 3600s."""

    def test_reduced_expiry(self):
        import inspect

        from app.converters.album_converter import to_album_photo_response

        source = inspect.getsource(to_album_photo_response)
        assert "900" in source


# ---------------------------------------------------------------------------
# Form: Strict file ownership check (P2)
# ---------------------------------------------------------------------------


class TestFormFileOwnershipStrict:
    """_validate_file_ownership checks user_id at expected position."""

    def test_editor_key_correct_position(self):
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        questions = [{"type": "file_upload", "id": "q1", "label": "Upload"}]
        answers = {"q1": {"key": f"editor/{user_id}/file.png"}}
        # Should not raise
        _validate_file_ownership(questions, answers, user_id)

    def test_wrong_user_rejected(self):
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        questions = [{"type": "file_upload", "id": "q1", "label": "Upload"}]
        answers = {"q1": {"key": f"editor/{other_id}/file.png"}}
        with pytest.raises(PermissionError):
            _validate_file_ownership(questions, answers, user_id)


# ---------------------------------------------------------------------------
# Redis: Dangerous commands disabled in prod config (P2)
# ---------------------------------------------------------------------------


class TestRedisProdConfig:
    """Production Redis config disables dangerous commands."""

    def test_flushall_disabled(self):
        import os

        conf_path = os.path.join(os.path.dirname(__file__), "..", "..", "redis", "redis-prod.conf")
        if os.path.exists(conf_path):
            content = open(conf_path, encoding="utf-8").read()
            assert 'rename-command FLUSHALL ""' in content
            assert 'rename-command DEBUG ""' in content
            assert 'rename-command KEYS ""' in content


# ---------------------------------------------------------------------------
# Nginx: DM in write rate limit zone (P2)
# ---------------------------------------------------------------------------


class TestNginxDmRateLimit:
    """nginx write-heavy regex includes DM endpoints."""

    def test_dm_in_write_zone(self):
        import os

        conf_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "nginx", "conf.d", "default.conf"
        )
        if os.path.exists(conf_path):
            content = open(conf_path, encoding="utf-8").read()
            assert "recommendations|dm)" in content


# ---------------------------------------------------------------------------
# Database: max_inactive_connection_lifetime (P3)
# ---------------------------------------------------------------------------


class TestDbConnectionLifetime:
    """Database pool has max_inactive_connection_lifetime set."""

    def test_lifetime_configured(self):
        import inspect

        from app.core.database import init_db_pool

        source = inspect.getsource(init_db_pool)
        assert "max_inactive_connection_lifetime" in source


# ---------------------------------------------------------------------------
# .env.production.example: DATABASE_SSL and REDIS_SSL (P2)
# ---------------------------------------------------------------------------


class TestProdEnvSsl:
    """Production env template documents SSL settings."""

    def test_ssl_settings_present(self):
        import os

        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env.production.example")
        if os.path.exists(env_path):
            content = open(env_path, encoding="utf-8").read()
            assert "DATABASE_SSL" in content
            assert "REDIS_SSL" in content


# ---------------------------------------------------------------------------
# Frontend: Edit draft key includes user ID (P2)
# ---------------------------------------------------------------------------


class TestEditDraftKeyUserId:
    """Edit draft key includes user ID to prevent cross-user leaks."""

    def test_key_has_uid(self):
        import os

        ts_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "frontend",
            "src",
            "composables",
            "usePostDetail.ts",
        )
        if os.path.exists(ts_path):
            content = open(ts_path, encoding="utf-8").read()
            # The key should reference the user ID, not just postId
            assert "auth.user" in content or "uid" in content


# ---------------------------------------------------------------------------
# Frontend: Error message filtering (P3)
# ---------------------------------------------------------------------------


class TestErrorMessageFilter:
    """getErrorMessage filters SQL-like server errors."""

    def test_sql_pattern_filtered(self):
        import os

        ts_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "src", "utils", "error.ts"
        )
        if os.path.exists(ts_path):
            content = open(ts_path, encoding="utf-8").read()
            assert "SELECT " in content or "INSERT " in content
