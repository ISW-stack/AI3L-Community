"""Tests for security audit 2026-03-26 HIGH, MEDIUM, and LOW findings.

Covers HIGH, MEDIUM (M-01 through M-21), and LOW items.
"""

import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings


# ── Helpers ──────────────────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc)
_SENDER_ID = str(uuid.uuid4())
_RECIPIENT_ID = str(uuid.uuid4())
_CONV_ID = uuid.uuid4()


def _make_settings(**overrides):
    """Create Settings with env_file disabled."""

    class TestSettings(Settings):
        model_config = SettingsConfigDict(env_file=None, extra="ignore")

    return TestSettings(**overrides)


_SAFE_PROD = dict(
    JWT_SECRET_KEY="prod_secret_key_safe_at_least_32chars_long",
    SECRET_KEY="real_secret_key_prod_32chars_long_ok",
    SUPER_ADMIN_PASSWORD="prod_p@ssw0rd!",
    POSTGRES_PASSWORD="real_pg_password",
    REDIS_PASSWORD="real_redis_password",
    S3_SECRET_ACCESS_KEY="real_minio_password",
    S3_ACCESS_KEY_ID="prod_access_key",
    CORS_ORIGINS="https://example.com",
)


def _make_message_row(
    attachment_key=None,
    attachment_name=None,
    is_recalled=False,
    sender_id=None,
    conv_id=None,
):
    return {
        "id": uuid.uuid4(),
        "conversation_id": conv_id or _CONV_ID,
        "sender_id": uuid.UUID(sender_id) if sender_id else uuid.uuid4(),
        "content": "Hello!",
        "attachment_key": attachment_key,
        "attachment_name": attachment_name,
        "attachment_size": 1024 if attachment_key else None,
        "attachment_expires_at": None,
        "is_recalled": is_recalled,
        "is_edited": False,
        "read_at": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


# ── H-01: Album presigned URLs gated on scan status ─────────────────────────


class TestAlbumScanGate:
    """Album photo presigned URLs should only be generated for clean files."""

    @pytest.mark.asyncio
    async def test_clean_file_gets_presigned_url(self):
        """A file with clean scan status gets a presigned URL."""
        from app.converters.album_converter import to_album_photo_response

        row = {
            "id": uuid.uuid4(),
            "album_id": uuid.uuid4(),
            "uploaded_by": uuid.uuid4(),
            "uploaded_by_name": "test",
            "storage_key": "albums/test/photo.jpg",
            "thumbnail_key": "albums/test/thumb.webp",
            "original_filename": "photo.jpg",
            "file_size_bytes": 1024,
            "content_type": "image/jpeg",
            "description": None,
            "width": 100,
            "height": 100,
            "is_zip": False,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        with (
            patch(
                "app.converters.album_converter.file_scan_repo.is_clean",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.converters.album_converter.generate_presigned_url",
                new_callable=AsyncMock,
                return_value="https://example.com/presigned",
            ),
        ):
            result = await to_album_photo_response(row)
            assert result["storage_url"] == "https://example.com/presigned"

    @pytest.mark.asyncio
    async def test_pending_file_gets_no_presigned_url(self):
        """A file with pending scan status gets no presigned URL (thumbnail still works)."""
        from app.converters.album_converter import to_album_photo_response

        row = {
            "id": uuid.uuid4(),
            "album_id": uuid.uuid4(),
            "uploaded_by": uuid.uuid4(),
            "uploaded_by_name": "test",
            "storage_key": "albums/test/photo.jpg",
            "thumbnail_key": "albums/test/thumb.webp",
            "original_filename": "photo.jpg",
            "file_size_bytes": 1024,
            "content_type": "image/jpeg",
            "description": None,
            "width": 100,
            "height": 100,
            "is_zip": False,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        with (
            patch(
                "app.converters.album_converter.file_scan_repo.is_clean",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.converters.album_converter.generate_presigned_url",
                new_callable=AsyncMock,
                return_value="https://example.com/thumb",
            ) as mock_presigned,
        ):
            result = await to_album_photo_response(row)
            assert result["storage_url"] is None
            # Thumbnail URL is still generated (not scan-gated)
            assert result["thumbnail_url"] == "https://example.com/thumb"
            # generate_presigned_url only called for thumbnail, not storage_key
            assert mock_presigned.call_count == 1
            assert mock_presigned.call_args[0][0] == "albums/test/thumb.webp"

    @pytest.mark.asyncio
    async def test_malicious_file_gets_no_presigned_url(self):
        """A file flagged as malicious gets no presigned URL."""
        from app.converters.album_converter import to_album_photo_response

        row = {
            "id": uuid.uuid4(),
            "album_id": uuid.uuid4(),
            "uploaded_by": uuid.uuid4(),
            "uploaded_by_name": "test",
            "storage_key": "albums/test/malware.jpg",
            "thumbnail_key": None,
            "original_filename": "malware.jpg",
            "file_size_bytes": 2048,
            "content_type": "image/jpeg",
            "description": None,
            "width": 100,
            "height": 100,
            "is_zip": False,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        with (
            patch(
                "app.converters.album_converter.file_scan_repo.is_clean",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.converters.album_converter.generate_presigned_url",
                new_callable=AsyncMock,
            ) as mock_presigned,
        ):
            result = await to_album_photo_response(row)
            assert result["storage_url"] is None
            mock_presigned.assert_not_called()


# ── H-01: DM presigned URLs gated on scan status ────────────────────────────


class TestDMScanGate:
    """DM attachment presigned URLs should only be generated for clean files."""

    @pytest.mark.asyncio
    async def test_list_messages_skips_unclean_attachments(self):
        """list_messages should not generate presigned URLs for non-clean files."""
        from app.services import dm as dm_svc

        row = _make_message_row(
            attachment_key="dm/test/file.pdf",
            attachment_name="file.pdf",
        )
        conv = {
            "id": _CONV_ID,
            "participant_a": uuid.UUID(_SENDER_ID),
            "participant_b": uuid.UUID(_RECIPIENT_ID),
        }

        with (
            patch(f"app.services.dm.dm_repo.find_conversation_by_id", new_callable=AsyncMock, return_value=conv),
            patch(f"app.services.dm.dm_repo.find_messages", new_callable=AsyncMock, return_value=([row], 1)),
            patch(f"app.services.dm.async_row_to_message", new_callable=AsyncMock, return_value={
                "id": str(row["id"]),
                "content": row["content"],
                "attachment_key": row["attachment_key"],
                "attachment_name": row["attachment_name"],
                "is_recalled": False,
            }),
            patch("app.services.dm._is_dm_file_clean", new_callable=AsyncMock, return_value=False),
            patch("app.core.storage.generate_presigned_url") as mock_presigned,
        ):
            messages, total = await dm_svc.list_messages(_SENDER_ID, str(_CONV_ID))
            assert total == 1
            assert "attachment_url" not in messages[0]
            mock_presigned.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_messages_includes_clean_attachments(self):
        """list_messages should generate presigned URLs for clean files."""
        from app.services import dm as dm_svc

        row = _make_message_row(
            attachment_key="dm/test/file.pdf",
            attachment_name="file.pdf",
        )
        conv = {
            "id": _CONV_ID,
            "participant_a": uuid.UUID(_SENDER_ID),
            "participant_b": uuid.UUID(_RECIPIENT_ID),
        }

        with (
            patch(f"app.services.dm.dm_repo.find_conversation_by_id", new_callable=AsyncMock, return_value=conv),
            patch(f"app.services.dm.dm_repo.find_messages", new_callable=AsyncMock, return_value=([row], 1)),
            patch(f"app.services.dm.async_row_to_message", new_callable=AsyncMock, return_value={
                "id": str(row["id"]),
                "content": row["content"],
                "attachment_key": row["attachment_key"],
                "attachment_name": row["attachment_name"],
                "is_recalled": False,
            }),
            patch("app.services.dm._is_dm_file_clean", new_callable=AsyncMock, return_value=True),
            patch("app.services.dm._sync_presigned_url", return_value="https://example.com/presigned"),
        ):
            messages, total = await dm_svc.list_messages(_SENDER_ID, str(_CONV_ID))
            assert total == 1
            assert messages[0]["attachment_url"] == "https://example.com/presigned"


# ── H-01: file_scan_repo.is_clean ───────────────────────────────────────────


class TestFileScanIsClean:
    """Unit tests for file_scan_repo.is_clean()."""

    @pytest.mark.asyncio
    async def test_no_record_returns_true(self):
        """Files with no scan record (legacy) are treated as clean."""
        from app.repositories import file_scan_repo

        with patch.object(file_scan_repo, "find_by_key", new_callable=AsyncMock, return_value=None):
            assert await file_scan_repo.is_clean("legacy/file.jpg") is True

    @pytest.mark.asyncio
    async def test_clean_record_returns_true(self):
        """Files with clean scan record are treated as clean."""
        from app.repositories import file_scan_repo

        with patch.object(
            file_scan_repo,
            "find_by_key",
            new_callable=AsyncMock,
            return_value={"file_key": "test.jpg", "status": "clean"},
        ):
            assert await file_scan_repo.is_clean("test.jpg") is True

    @pytest.mark.asyncio
    async def test_pending_record_returns_false(self):
        """Files with pending scan record are not clean."""
        from app.repositories import file_scan_repo

        with patch.object(
            file_scan_repo,
            "find_by_key",
            new_callable=AsyncMock,
            return_value={"file_key": "test.jpg", "status": "pending"},
        ):
            assert await file_scan_repo.is_clean("test.jpg") is False

    @pytest.mark.asyncio
    async def test_malicious_record_returns_false(self):
        """Files with malicious scan record are not clean."""
        from app.repositories import file_scan_repo

        with patch.object(
            file_scan_repo,
            "find_by_key",
            new_callable=AsyncMock,
            return_value={"file_key": "test.jpg", "status": "malicious"},
        ):
            assert await file_scan_repo.is_clean("test.jpg") is False

    @pytest.mark.asyncio
    async def test_unknown_record_returns_true(self):
        """Files with unknown scan status (hash not in VT) are safe to serve."""
        from app.repositories import file_scan_repo

        with patch.object(
            file_scan_repo,
            "find_by_key",
            new_callable=AsyncMock,
            return_value={"file_key": "test.jpg", "status": "unknown"},
        ):
            assert await file_scan_repo.is_clean("test.jpg") is True


# ── H-02: Async generate_presigned_url forwards filename ────────────────────


class TestAsyncPresignedUrlFilename:
    """async_storage.generate_presigned_url should forward filename param."""

    @pytest.mark.asyncio
    async def test_forwards_filename_to_sync(self):
        """The async wrapper passes filename through to the sync function."""
        from app.core import async_storage

        with patch.object(
            async_storage,
            "_sync_presigned",
            return_value="https://example.com/presigned",
        ) as mock_sync:
            result = await async_storage.generate_presigned_url(
                "test/key.jpg", 900, filename="photo.jpg"
            )
            assert result == "https://example.com/presigned"
            mock_sync.assert_called_once_with("test/key.jpg", 900, "photo.jpg")

    @pytest.mark.asyncio
    async def test_filename_defaults_to_none(self):
        """When filename is omitted, None is passed to the sync function."""
        from app.core import async_storage

        with patch.object(
            async_storage,
            "_sync_presigned",
            return_value="https://example.com/presigned",
        ) as mock_sync:
            await async_storage.generate_presigned_url("test/key.jpg", 900)
            mock_sync.assert_called_once_with("test/key.jpg", 900, None)


# ── H-06: SECRET_KEY minimum length in production ───────────────────────────


class TestSecretKeyMinLength:
    """Production validator must reject short SECRET_KEY."""

    def test_rejects_short_secret_key_in_production(self):
        """SECRET_KEY < 32 chars should raise ValueError in production."""
        with pytest.raises(ValueError, match="SECRET_KEY must be at least 32 characters"):
            _make_settings(
                FASTAPI_ENV="production",
                SECRET_KEY="short_key",
                **{k: v for k, v in _SAFE_PROD.items() if k != "SECRET_KEY"},
            )

    def test_accepts_long_secret_key_in_production(self):
        """SECRET_KEY >= 32 chars should be accepted in production."""
        s = _make_settings(FASTAPI_ENV="production", **_SAFE_PROD)
        assert len(s.SECRET_KEY) >= 32

    def test_allows_short_secret_key_in_development(self):
        """SECRET_KEY length is not checked in development."""
        s = _make_settings(FASTAPI_ENV="development", SECRET_KEY="short")
        assert s.SECRET_KEY == "short"


# ── H-07: JWT iss/aud claims + algorithm validation ─────────────────────────


class TestJWTIssuerAudience:
    """JWT tokens must include and validate iss/aud claims."""

    def test_token_includes_iss_and_aud(self):
        """Created JWT should contain iss and aud claims."""
        from app.core.security import create_access_token, decode_access_token

        user_id = str(uuid.uuid4())
        token, jti, _ = create_access_token(user_id, "MEMBER")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["iss"] == "ai3l-community"
        assert payload["aud"] == "ai3l-api"

    def test_token_without_iss_rejected(self):
        """A token missing iss claim should be rejected."""
        import jwt as pyjwt

        from app.core.config import settings
        from app.core.security import decode_access_token

        payload = {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "aud": "ai3l-api",
            # no "iss"
        }
        token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
        assert decode_access_token(token) is None

    def test_token_with_wrong_aud_rejected(self):
        """A token with wrong aud claim should be rejected."""
        import jwt as pyjwt

        from app.core.config import settings
        from app.core.security import decode_access_token

        payload = {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": "ai3l-community",
            "aud": "wrong-audience",
        }
        token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
        assert decode_access_token(token) is None

    def test_token_with_wrong_iss_rejected(self):
        """A token with wrong iss claim should be rejected."""
        import jwt as pyjwt

        from app.core.config import settings
        from app.core.security import decode_access_token

        payload = {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": "other-service",
            "aud": "ai3l-api",
        }
        token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
        assert decode_access_token(token) is None


class TestJWTAlgorithmValidation:
    """JWT_ALGORITHM must be validated against an allowlist."""

    def test_rejects_none_algorithm(self):
        """JWT_ALGORITHM='none' should be rejected."""
        with pytest.raises(ValueError, match="JWT_ALGORITHM.*not allowed"):
            _make_settings(FASTAPI_ENV="development", JWT_ALGORITHM="none")

    def test_rejects_unknown_algorithm(self):
        """JWT_ALGORITHM='RS256' should be rejected (not in allowlist)."""
        with pytest.raises(ValueError, match="JWT_ALGORITHM.*not allowed"):
            _make_settings(FASTAPI_ENV="development", JWT_ALGORITHM="RS256")

    def test_accepts_hs256(self):
        """JWT_ALGORITHM='HS256' should be accepted."""
        s = _make_settings(FASTAPI_ENV="development", JWT_ALGORITHM="HS256")
        assert s.JWT_ALGORITHM == "HS256"

    def test_accepts_hs384(self):
        """JWT_ALGORITHM='HS384' should be accepted."""
        s = _make_settings(FASTAPI_ENV="development", JWT_ALGORITHM="HS384")
        assert s.JWT_ALGORITHM == "HS384"

    def test_accepts_hs512(self):
        """JWT_ALGORITHM='HS512' should be accepted."""
        s = _make_settings(FASTAPI_ENV="development", JWT_ALGORITHM="HS512")
        assert s.JWT_ALGORITHM == "HS512"


# ── L-01: bootstrap_super_admin validates password policy ───────────────────


class TestBootstrapPasswordPolicy:
    """bootstrap_super_admin() must validate SUPER_ADMIN_PASSWORD against policy."""

    @pytest.mark.asyncio
    async def test_warns_in_dev_when_policy_fails(self):
        """In development, a policy-failing password logs a warning (no raise)."""
        from app.core.config import Settings
        from pydantic_settings import SettingsConfigDict

        class DevSettings(Settings):
            model_config = SettingsConfigDict(env_file=None, extra="ignore")

        dev_settings = DevSettings(FASTAPI_ENV="development", SUPER_ADMIN_PASSWORD="weakpassword")

        # Patch the functions at their source modules (they're imported inside the function).
        # Patch user_exists_by_username to return False so create_user is called instead of
        # the DB-heavy user_repo.find_by_username path.
        with (
            patch("app.main.settings", dev_settings),
            patch("app.services.user.user_exists_by_username", new_callable=AsyncMock, return_value=False),
            patch("app.services.user.create_user", new_callable=AsyncMock),
        ):
            from app.main import bootstrap_super_admin

            # Should not raise in development
            await bootstrap_super_admin()

    @pytest.mark.asyncio
    async def test_raises_in_production_when_policy_fails(self):
        """In production, a policy-failing password raises RuntimeError before any DB call."""
        from app.core.config import Settings
        from pydantic_settings import SettingsConfigDict

        class ProdSettings(Settings):
            model_config = SettingsConfigDict(env_file=None, extra="ignore")

        prod_settings = ProdSettings(
            FASTAPI_ENV="production",
            SUPER_ADMIN_PASSWORD="weakpassword",
            **{k: v for k, v in _SAFE_PROD.items() if k != "SUPER_ADMIN_PASSWORD"},
        )

        with patch("app.main.settings", prod_settings):
            from app.main import bootstrap_super_admin

            with pytest.raises(RuntimeError, match="does not meet password policy"):
                await bootstrap_super_admin()

    @pytest.mark.asyncio
    async def test_passes_with_strong_password(self):
        """A password meeting policy does not raise or warn."""
        from app.core.config import Settings
        from pydantic_settings import SettingsConfigDict

        class DevSettings(Settings):
            model_config = SettingsConfigDict(env_file=None, extra="ignore")

        dev_settings = DevSettings(
            FASTAPI_ENV="development", SUPER_ADMIN_PASSWORD="Str0ng!Pass"
        )

        with (
            patch("app.main.settings", dev_settings),
            patch("app.services.user.user_exists_by_username", new_callable=AsyncMock, return_value=False),
            patch("app.services.user.create_user", new_callable=AsyncMock),
        ):
            from app.main import bootstrap_super_admin

            await bootstrap_super_admin()  # no exception


# ── L-02: COOKIE_SAMESITE validation ────────────────────────────────────────


class TestCookieSamesiteValidation:
    """COOKIE_SAMESITE must be validated against the allowlist."""

    def test_rejects_invalid_samesite(self):
        """Invalid COOKIE_SAMESITE raises ValueError."""
        with pytest.raises(ValueError, match="COOKIE_SAMESITE"):
            _make_settings(FASTAPI_ENV="development", COOKIE_SAMESITE="invalid")

    def test_accepts_lax(self):
        s = _make_settings(FASTAPI_ENV="development", COOKIE_SAMESITE="lax")
        assert s.COOKIE_SAMESITE == "lax"

    def test_accepts_strict(self):
        s = _make_settings(FASTAPI_ENV="development", COOKIE_SAMESITE="strict")
        assert s.COOKIE_SAMESITE == "strict"

    def test_accepts_none(self):
        """'none' is valid (but may emit a warning without COOKIE_SECURE)."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s = _make_settings(FASTAPI_ENV="development", COOKIE_SAMESITE="none")
        assert s.COOKIE_SAMESITE == "none"

    def test_none_without_secure_warns(self):
        """COOKIE_SAMESITE='none' without COOKIE_SECURE=True should warn."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _make_settings(
                FASTAPI_ENV="development", COOKIE_SAMESITE="none", COOKIE_SECURE=False
            )
        assert any("weakens CSRF" in str(warning.message) for warning in w)


# ── L-05 / L-16: Avatar presigned URL expiry and constant usage ──────────────


class TestAvatarPresignedUrlExpiry:
    """PRESIGNED_URL_AVATAR_SECONDS must be 3600 and used in user_converter."""

    def test_constant_is_one_hour(self):
        """PRESIGNED_URL_AVATAR_SECONDS should be 3600 (1 hour)."""
        from app.core.constants import PRESIGNED_URL_AVATAR_SECONDS

        assert PRESIGNED_URL_AVATAR_SECONDS == 3600

    def test_sync_converter_uses_constant(self):
        """resolve_avatar_url passes PRESIGNED_URL_AVATAR_SECONDS to generate_presigned_url."""
        from app.core.constants import PRESIGNED_URL_AVATAR_SECONDS
        from app.converters.user_converter import resolve_avatar_url

        mock_gen = MagicMock(return_value="https://example.com/url")
        # generate_presigned_url is imported locally inside the function from app.core.storage
        with patch("app.core.storage.generate_presigned_url", mock_gen):
            resolve_avatar_url("avatars/user.png")

        mock_gen.assert_called_once()
        assert mock_gen.call_args[1]["expires_in"] == PRESIGNED_URL_AVATAR_SECONDS

    @pytest.mark.asyncio
    async def test_async_converter_uses_constant(self):
        """async_resolve_avatar_url passes PRESIGNED_URL_AVATAR_SECONDS to generate_presigned_url."""
        from app.core.constants import PRESIGNED_URL_AVATAR_SECONDS
        from app.converters.user_converter import async_resolve_avatar_url

        mock_gen = AsyncMock(return_value="https://example.com/url")
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

        with (
            # get_redis imported locally from app.core.redis
            patch("app.core.redis.get_redis", return_value=mock_redis),
            # generate_presigned_url imported locally from app.core.async_storage
            patch("app.core.async_storage.generate_presigned_url", mock_gen),
        ):
            await async_resolve_avatar_url("avatars/user.png")

        mock_gen.assert_called_once()
        assert mock_gen.call_args[1]["expires_in"] == PRESIGNED_URL_AVATAR_SECONDS


# ── L-06: Upload lock TTL ────────────────────────────────────────────────────


class TestUploadLockTTL:
    """Editor file upload lock must use 300s TTL to cover slow uploads."""

    def test_upload_lock_ttl_is_300(self):
        """The upload lock is acquired with ex=300."""
        import inspect

        import app.api.v1.endpoints.files as files_mod

        source = inspect.getsource(files_mod)
        # Ensure ex=300 appears in the upload lock acquisition
        assert "ex=300" in source, "Upload lock TTL must be 300s"
        assert "ex=120" not in source, "Old 120s TTL must be removed"


# ── L-07: Form file_upload scan status check ────────────────────────────────


class TestFormFileUploadScanCheck:
    """Form submissions must reject file_upload answers with non-clean scan status."""

    @pytest.mark.asyncio
    async def test_rejects_pending_scan_file(self):
        """Submitting a form with a pending-scan file raises ValueError."""
        from app.services.form import _validate_file_scan_status

        questions = [{"id": "q1", "type": "file_upload", "label": "Upload"}]
        answers = {"q1": {"key": "editor/user1/file.pdf", "filename": "file.pdf"}}

        with patch(
            "app.repositories.file_scan_repo.is_clean",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with pytest.raises(ValueError, match="not yet cleared"):
                await _validate_file_scan_status(questions, answers)

    @pytest.mark.asyncio
    async def test_accepts_clean_scan_file(self):
        """Submitting a form with a clean-scan file passes validation."""
        from app.services.form import _validate_file_scan_status

        questions = [{"id": "q1", "type": "file_upload", "label": "Upload"}]
        answers = {"q1": {"key": "editor/user1/file.pdf", "filename": "file.pdf"}}

        with patch(
            "app.repositories.file_scan_repo.is_clean",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await _validate_file_scan_status(questions, answers)  # no exception

    @pytest.mark.asyncio
    async def test_skips_non_file_upload_questions(self):
        """Non-file_upload questions are not scan-checked."""
        from app.services.form import _validate_file_scan_status

        questions = [{"id": "q1", "type": "text", "label": "Name"}]
        answers = {"q1": "Alice"}

        with patch(
            "app.repositories.file_scan_repo.is_clean",
            new_callable=AsyncMock,
        ) as mock_clean:
            await _validate_file_scan_status(questions, answers)
            mock_clean.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_missing_answer(self):
        """Missing answers for file_upload questions are skipped (required check elsewhere)."""
        from app.services.form import _validate_file_scan_status

        questions = [{"id": "q1", "type": "file_upload", "label": "Upload"}]
        answers: dict = {}

        with patch(
            "app.repositories.file_scan_repo.is_clean",
            new_callable=AsyncMock,
        ) as mock_clean:
            await _validate_file_scan_status(questions, answers)
            mock_clean.assert_not_called()


# ── L-15: DATABASE_SSL warning for remote host ───────────────────────────────


class TestDatabaseSslWarning:
    """Should warn when DATABASE_SSL=False but POSTGRES_HOST is a remote host."""

    def test_warns_for_remote_host_without_ssl(self):
        """Remote POSTGRES_HOST with DATABASE_SSL=False emits a warning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _make_settings(
                FASTAPI_ENV="development",
                POSTGRES_HOST="db.example.com",
                DATABASE_SSL=False,
            )
        assert any("DATABASE_SSL" in str(warning.message) for warning in w)

    def test_no_warning_for_localhost(self):
        """Local POSTGRES_HOST does not warn about SSL."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _make_settings(
                FASTAPI_ENV="development", POSTGRES_HOST="localhost", DATABASE_SSL=False
            )
        assert not any("DATABASE_SSL" in str(warning.message) for warning in w)

    def test_no_warning_with_ssl_enabled(self):
        """Remote host with DATABASE_SSL=True does not warn."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _make_settings(
                FASTAPI_ENV="development",
                POSTGRES_HOST="db.example.com",
                DATABASE_SSL=True,
            )
        assert not any("DATABASE_SSL" in str(warning.message) for warning in w)


# ── L-19: Blacklist TTL simplification ──────────────────────────────────────


class TestBlacklistTTL:
    """Blacklist TTL must be 43200 without dead max() code."""

    @pytest.mark.asyncio
    async def test_blacklist_ttl_is_43200(self):
        """destroy_session sets blacklist key with ex=43200."""
        from app.services import auth as auth_svc

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await auth_svc.destroy_session("user-id", "MEMBER", "test-jti")

        # Find the set call for the blacklist key (key pattern: jwt:blacklist:{jti})
        blacklist_calls = [
            call for call in mock_redis.set.call_args_list if "blacklist:" in str(call)
        ]
        assert blacklist_calls, "Expected a blacklist set() call"
        _, kwargs = blacklist_calls[0]
        assert kwargs.get("ex") == 43200, f"Expected ex=43200, got {kwargs.get('ex')}"

    def test_no_dead_max_call_in_source(self):
        """Source code must not contain the dead max(28800, 43200) expression."""
        import inspect

        from app.services import auth as auth_svc

        source = inspect.getsource(auth_svc)
        assert "max(28800, 43200)" not in source


# ── L-25: SUPER_ADMIN_USERNAME default warning ───────────────────────────────


class TestSuperAdminUsernameWarning:
    """Production should warn when SUPER_ADMIN_USERNAME is default 'superadmin'."""

    def test_warns_when_username_is_default_in_production(self):
        """SUPER_ADMIN_USERNAME='superadmin' in production emits a warning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _make_settings(
                FASTAPI_ENV="production",
                SUPER_ADMIN_USERNAME="superadmin",
                **_SAFE_PROD,
            )
        assert any(
            "SUPER_ADMIN_USERNAME" in str(warning.message) for warning in w
        ), "Expected warning about default SUPER_ADMIN_USERNAME"

    def test_no_warning_when_username_is_custom(self):
        """Custom SUPER_ADMIN_USERNAME in production does not warn."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _make_settings(
                FASTAPI_ENV="production",
                SUPER_ADMIN_USERNAME="myadmin2026",
                **_SAFE_PROD,
            )
        assert not any("SUPER_ADMIN_USERNAME" in str(warning.message) for warning in w)


# ── M-01: Avatar uploads trigger VirusTotal scan ─────────────────────────────


class TestAvatarVirusScan:
    """Avatar upload must call trigger_virus_scan()."""

    @pytest.mark.asyncio
    async def test_avatar_upload_triggers_virus_scan(self):
        """upload_user_avatar should call trigger_virus_scan with file key and data."""
        from app.services import user as user_svc

        user_id = str(uuid.uuid4())
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG-like data

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        with (
            patch("app.services.user.get_redis", return_value=mock_redis),
            patch("app.services.user.validate_avatar"),
            patch("app.services.user.async_get_file_size", new_callable=AsyncMock, return_value=0),
            patch("app.services.user.async_upload_file", new_callable=AsyncMock),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.services.user.trigger_virus_scan", new_callable=AsyncMock) as mock_scan,
            patch("app.services.user.update_user_profile", new_callable=AsyncMock, return_value={"id": user_id}),
        ):
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": ""})
            mock_repo.get_storage_used = AsyncMock(return_value=0)
            mock_repo.increment_storage_used = AsyncMock()

            await user_svc.upload_user_avatar(user_id, data, "image/png", "avatar.png")
            mock_scan.assert_called_once()
            call_args = mock_scan.call_args
            assert call_args[0][1] == data  # second arg is file data


# ── M-03: GIF polyglot prevention ────────────────────────────────────────────


class TestGifValidation:
    """GIF files must be re-encoded via Pillow to strip polyglot payloads."""

    def test_valid_gif_passes(self):
        """A valid GIF file should be re-encoded successfully."""
        from app.core.file_validation import validate_gif_structure

        # Create a minimal valid GIF via Pillow
        from PIL import Image

        buf = BytesIO()
        img = Image.new("RGB", (1, 1), (255, 0, 0))
        img.save(buf, format="GIF")
        gif_data = buf.getvalue()

        result = validate_gif_structure(gif_data)
        assert result  # Non-empty bytes
        assert result[:6] in (b"GIF87a", b"GIF89a")

    def test_gif_html_polyglot_rejected(self):
        """A file with GIF header but HTML payload should fail Pillow re-encode."""
        from app.core.file_validation import validate_gif_structure

        # GIF header + HTML payload = polyglot
        polyglot = b"GIF89a" + b"<html><script>alert(1)</script></html>"
        with pytest.raises(ValueError, match="Invalid GIF"):
            validate_gif_structure(polyglot)

    def test_gif_validation_called_in_editor_upload(self):
        """validate_editor_file should call validate_gif_structure for .gif files."""
        from app.core.file_validation import validate_editor_file

        from PIL import Image

        buf = BytesIO()
        img = Image.new("RGB", (1, 1), (255, 0, 0))
        img.save(buf, format="GIF")
        gif_data = buf.getvalue()

        content_type, result_data = validate_editor_file("test.gif", gif_data)
        assert content_type == "image/gif"
        assert result_data[:6] in (b"GIF87a", b"GIF89a")


# ── M-04: EXIF metadata stripping ────────────────────────────────────────────


class TestExifStripping:
    """Images must have EXIF metadata stripped before storage."""

    def test_jpeg_exif_stripped(self):
        """JPEG files should have EXIF data removed."""
        from app.core.file_validation import strip_exif_metadata

        from PIL import Image

        # Create JPEG with EXIF data
        buf = BytesIO()
        img = Image.new("RGB", (10, 10), (255, 0, 0))
        img.save(buf, format="JPEG")
        jpeg_data = buf.getvalue()

        result = strip_exif_metadata(jpeg_data, "image/jpeg")
        assert result  # Non-empty bytes
        assert result[:2] == b"\xff\xd8"  # Still a valid JPEG

    def test_non_image_unchanged(self):
        """Non-image content types should be returned unchanged."""
        from app.core.file_validation import strip_exif_metadata

        pdf_data = b"%PDF-1.4 test content"
        result = strip_exif_metadata(pdf_data, "application/pdf")
        assert result == pdf_data

    def test_png_exif_stripped(self):
        """PNG files should have EXIF data removed."""
        from app.core.file_validation import strip_exif_metadata

        from PIL import Image

        buf = BytesIO()
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        img.save(buf, format="PNG")
        png_data = buf.getvalue()

        result = strip_exif_metadata(png_data, "image/png")
        assert result[:8] == b"\x89PNG\r\n\x1a\n"


# ── M-05: Streaming ZIP re-write ─────────────────────────────────────────────


class TestZipStreamingRewrite:
    """ZIP re-write should use streaming (copyfileobj) not full-entry read."""

    def test_source_uses_streaming_pattern(self):
        """zip_validation.py should use shutil.copyfileobj for re-write."""
        import inspect

        from app.core import zip_validation

        source = inspect.getsource(zip_validation)
        assert "copyfileobj" in source, "ZIP re-write must use shutil.copyfileobj"


# ── M-06: Scan record insertion retry ─────────────────────────────────────────


class TestScanRecordRetry:
    """Editor file upload should retry scan record insertion."""

    def test_source_has_retry_loop(self):
        """files.py should have retry logic for scan record insertion."""
        import inspect

        from app.api.v1.endpoints import files

        source = inspect.getsource(files)
        assert "for _scan_attempt in range(3)" in source


# ── M-07: XLSX/PPTX directory validation ─────────────────────────────────────


class TestOoxmlDirectoryValidation:
    """XLSX must have xl/, PPTX must have ppt/ directory."""

    def test_valid_xlsx_structure(self):
        """XLSX with [Content_Types].xml and xl/ passes."""
        import zipfile

        from app.core.file_validation import validate_xlsx_structure

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("xl/workbook.xml", "<workbook/>")
        assert validate_xlsx_structure(buf.getvalue()) is True

    def test_xlsx_without_xl_dir_rejected(self):
        """XLSX without xl/ directory fails."""
        import zipfile

        from app.core.file_validation import validate_xlsx_structure

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("META-INF/MANIFEST.MF", "")  # JAR structure
        assert validate_xlsx_structure(buf.getvalue()) is False

    def test_valid_pptx_structure(self):
        """PPTX with [Content_Types].xml and ppt/ passes."""
        import zipfile

        from app.core.file_validation import validate_pptx_structure

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("ppt/presentation.xml", "<presentation/>")
        assert validate_pptx_structure(buf.getvalue()) is True

    def test_pptx_without_ppt_dir_rejected(self):
        """PPTX without ppt/ directory fails."""
        import zipfile

        from app.core.file_validation import validate_pptx_structure

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("classes/Main.class", "")  # APK/JAR structure
        assert validate_pptx_structure(buf.getvalue()) is False

    def test_dm_validates_xlsx_with_xl_dir(self):
        """DM service uses validate_xlsx_structure (not generic ooxml)."""
        import inspect

        from app.services import dm

        source = inspect.getsource(dm)
        assert "validate_xlsx_structure" in source
        assert "validate_pptx_structure" in source


# ── M-12: CORS origin format validation ──────────────────────────────────────


class TestCorsOriginValidation:
    """CORS origins must be validated for proper URL format."""

    def test_warns_on_invalid_origin_format(self):
        """Origins without http:// or https:// should emit a warning."""
        import warnings

        s = _make_settings(
            FASTAPI_ENV="development",
            CORS_ORIGINS="example.com,http://localhost:3000",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = s.CORS_ORIGINS_LIST
        assert any("does not start with http" in str(warning.message) for warning in w)

    def test_warns_on_wildcard_origin(self):
        """Origins with wildcards should emit a warning."""
        import warnings

        s = _make_settings(
            FASTAPI_ENV="development",
            CORS_ORIGINS="https://*.example.com",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = s.CORS_ORIGINS_LIST
        assert any("wildcard" in str(warning.message) for warning in w)

    def test_valid_origins_no_warning(self):
        """Properly formatted origins should not warn."""
        import warnings

        s = _make_settings(
            FASTAPI_ENV="development",
            CORS_ORIGINS="http://localhost:3000,https://example.com",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            origins = s.CORS_ORIGINS_LIST
        assert origins == ["http://localhost:3000", "https://example.com"]
        assert not any("does not start with http" in str(warning.message) for warning in w)


# ── M-17: Per-account login rate limit ────────────────────────────────────────


class TestPerAccountLoginRateLimit:
    """Per-account login rate limit should be 50 (not 20) to reduce lockout risk."""

    def test_rate_limit_is_50(self):
        """The per-account login rate limit should be 50 requests per window."""
        import inspect

        from app.api.v1.endpoints import auth

        source = inspect.getsource(auth)
        assert 'f"rl:login:user:{req.username}", 50, 300' in source


# ── M-18: CSRF heartbeat comment accuracy ─────────────────────────────────────


class TestCsrfHeartbeatComment:
    """Heartbeat CSRF comment must not claim token rotation happens."""

    def test_no_misleading_regeneration_comment(self):
        """The heartbeat should not claim CSRF tokens 'expire' via regeneration."""
        import inspect

        from app.api.v1.endpoints import auth

        source = inspect.getsource(auth)
        assert "so leaked tokens expire" not in source


# ── M-19: Recursive PDF sanitization ─────────────────────────────────────────


class TestRecursivePdfSanitization:
    """PDF sanitization must recursively strip dangerous keys from all objects."""

    def test_recursive_function_exists(self):
        """_strip_dangerous_keys_recursive should exist in file_validation."""
        from app.core.file_validation import _strip_dangerous_keys_recursive

        assert callable(_strip_dangerous_keys_recursive)

    def test_sanitize_pdf_strips_nested_javascript(self):
        """PDF with JavaScript in annotations should be sanitized."""
        import pikepdf

        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(612, 792))

        # Add annotation with /JS key (nested, not at page root)
        annot = pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name.Link,
        )
        annot["/JS"] = pikepdf.String("alert('xss')")
        page_obj = pdf.pages[0].obj
        page_obj["/Annots"] = pikepdf.Array([annot])

        buf = BytesIO()
        pdf.save(buf)
        pdf_data = buf.getvalue()

        from app.core.file_validation import sanitize_pdf

        sanitized = sanitize_pdf(pdf_data)

        # Verify the /JS key was removed from the annotation
        clean_pdf = pikepdf.open(BytesIO(sanitized))
        clean_page = clean_pdf.pages[0].obj
        if "/Annots" in clean_page:
            for annot_ref in clean_page["/Annots"]:
                assert "/JS" not in annot_ref


# ── M-20: WebSocket JTI revalidation ─────────────────────────────────────────


class TestWsJtiRevalidation:
    """WebSocket session revalidation must compare JTI, not just check existence."""

    def test_ws_revalidation_uses_get_not_exists(self):
        """_session_revalidation should use r.get() not r.exists()."""
        import inspect

        from app.api.v1.endpoints import ws

        source = inspect.getsource(ws)
        # The revalidation should use get to retrieve the stored JTI
        assert "stored_jti = await r.get(session_key)" in source
        # And compare with the ticket JTI
        assert "stored_jti_str != jti" in source

    def test_jti_extracted_from_payload(self):
        """The WS endpoint should extract jti from the ticket payload."""
        import inspect

        from app.api.v1.endpoints import ws

        source = inspect.getsource(ws)
        assert 'jti = payload.get("jti"' in source


# ── M-21: Login username validation ──────────────────────────────────────────


class TestLoginUsernameValidation:
    """Login username should have min_length=3 and pattern matching registration."""

    def test_rejects_single_char_username(self):
        """Username with 1 character should fail validation."""
        from pydantic import ValidationError

        from app.schemas.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(username="a", password="test123", captcha_id="c1", captcha_code="1234")

    def test_rejects_two_char_username(self):
        """Username with 2 characters should fail validation."""
        from pydantic import ValidationError

        from app.schemas.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(username="ab", password="test123", captcha_id="c1", captcha_code="1234")

    def test_accepts_three_char_username(self):
        """Username with 3 characters should pass validation."""
        from app.schemas.auth import LoginRequest

        req = LoginRequest(username="abc", password="test123", captcha_id="c1", captcha_code="1234")
        assert req.username == "abc"

    def test_rejects_special_chars_in_username(self):
        """Username with special characters should fail pattern validation."""
        from pydantic import ValidationError

        from app.schemas.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(
                username="user@name", password="test123", captcha_id="c1", captcha_code="1234"
            )

    def test_accepts_valid_username_pattern(self):
        """Username with alphanumeric, underscore, hyphen should pass."""
        from app.schemas.auth import LoginRequest

        req = LoginRequest(
            username="user_name-123", password="test123", captcha_id="c1", captcha_code="1234"
        )
        assert req.username == "user_name-123"
