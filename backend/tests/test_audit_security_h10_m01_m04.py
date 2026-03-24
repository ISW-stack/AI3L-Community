"""Tests for auth/security audit fixes H-10, M-01, M-02, M-03, M-04,
L-01, L-03, L-06, L-11, L-14, L-15.

Covers: captcha CSPRNG + timing-safe comparison, RETURNING column restriction,
X-Forwarded-For index, application rate limiting, destroy_session JTI
ownership, invite_code max_length, file cache-control, presigned URL
filename escaping, display_name min_length, audit UUID validation.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── H-10: Captcha uses secrets.choice (CSPRNG) ────────────────────────


class TestCaptchaCSPRNG:
    """H-10: captcha code must use secrets module, not random."""

    def test_captcha_imports_secrets_not_random(self):
        """captcha.py should use secrets, not random."""
        import inspect

        from app.services import captcha

        source = inspect.getsource(captcha)
        assert "secrets.choice" in source
        assert "random.choices" not in source

    @pytest.mark.anyio
    async def test_generate_captcha_code_length(self, mock_redis):
        """Generated captcha code has expected length."""
        from app.core.constants import CAPTCHA_LENGTH

        with (
            patch("app.services.captcha.get_redis", return_value=mock_redis),
            patch("app.services.captcha.ImageCaptcha") as mock_img,
        ):
            # Mock the image generation
            mock_instance = MagicMock()
            mock_img.return_value = mock_instance
            mock_image = MagicMock()
            mock_instance.generate_image.return_value = mock_image
            mock_image.save = MagicMock()

            captcha_id, image_b64 = await _generate_captcha_and_capture_code(mock_redis)

            # Verify the code stored in Redis has the correct length
            call_args = mock_redis.set.call_args
            stored_code = call_args[0][1]  # second positional arg is the code
            assert len(stored_code) == CAPTCHA_LENGTH

    @pytest.mark.anyio
    async def test_generate_captcha_code_chars_valid(self, mock_redis):
        """Generated code only contains allowed characters."""
        import string

        allowed = set(
            string.ascii_uppercase.replace("O", "").replace("I", "")
            + string.digits.replace("0", "").replace("1", "")
        )

        with (
            patch("app.services.captcha.get_redis", return_value=mock_redis),
            patch("app.services.captcha.ImageCaptcha") as mock_img,
        ):
            mock_instance = MagicMock()
            mock_img.return_value = mock_instance
            mock_image = MagicMock()
            mock_instance.generate_image.return_value = mock_image
            mock_image.save = MagicMock()

            await _generate_captcha_and_capture_code(mock_redis)

            stored_code = mock_redis.set.call_args[0][1]
            for ch in stored_code:
                assert ch in allowed, f"Character '{ch}' not in allowed set"


async def _generate_captcha_and_capture_code(mock_redis):
    """Helper: call generate_captcha and return (captcha_id, image_b64)."""
    from app.services.captcha import generate_captcha

    return await generate_captcha()


# ── M-01: Captcha timing-safe comparison ───────────────────────────────


class TestCaptchaTimingSafe:
    """M-01: verify_captcha must use hmac.compare_digest."""

    def test_verify_uses_hmac_compare_digest(self):
        """Source code uses hmac.compare_digest, not == for comparison."""
        import inspect

        from app.services import captcha

        source = inspect.getsource(captcha.verify_captcha)
        assert "hmac.compare_digest" in source
        assert "==" not in source

    @pytest.mark.anyio
    async def test_verify_captcha_correct_code(self, mock_redis):
        """verify_captcha returns True for matching code."""
        from app.services.captcha import verify_captcha

        mock_redis.getdel = AsyncMock(return_value="ABCD")

        with patch("app.services.captcha.get_redis", return_value=mock_redis):
            result = await verify_captcha("cap-id", "abcd")

        assert result is True

    @pytest.mark.anyio
    async def test_verify_captcha_wrong_code(self, mock_redis):
        """verify_captcha returns False for non-matching code."""
        from app.services.captcha import verify_captcha

        mock_redis.getdel = AsyncMock(return_value="ABCD")

        with patch("app.services.captcha.get_redis", return_value=mock_redis):
            result = await verify_captcha("cap-id", "WXYZ")

        assert result is False

    @pytest.mark.anyio
    async def test_verify_captcha_expired(self, mock_redis):
        """verify_captcha returns False when captcha expired (None from Redis)."""
        from app.services.captcha import verify_captcha

        mock_redis.getdel = AsyncMock(return_value=None)

        with patch("app.services.captcha.get_redis", return_value=mock_redis):
            result = await verify_captcha("expired-id", "ABCD")

        assert result is False

    @pytest.mark.anyio
    async def test_verify_captcha_case_insensitive(self, mock_redis):
        """verify_captcha comparison is case-insensitive."""
        from app.services.captcha import verify_captcha

        mock_redis.getdel = AsyncMock(return_value="AbCd")

        with patch("app.services.captcha.get_redis", return_value=mock_redis):
            result = await verify_captcha("cap-id", "aBcD")

        assert result is True


# ── M-02: RETURNING * replaced with explicit columns ──────────────────


class TestRegisterReturningColumns:
    """M-02: register_new_user must not use RETURNING * (excludes password_hash)."""

    def test_register_sql_no_returning_star(self):
        """Source code should not contain RETURNING *."""
        import inspect

        from app.services import auth

        source = inspect.getsource(auth.register_new_user)
        assert "RETURNING *" not in source
        assert "RETURNING id" in source
        # Should NOT return password_hash
        assert "password_hash" not in source.split("RETURNING")[1].split('"""')[0]


# ── M-03: X-Forwarded-For takes first IP ──────────────────────────────


class TestXForwardedForIndex:
    """M-03: get_client_ip must use [0] (original client) not [-1] (last proxy)."""

    def _make_request(self, headers_map):
        """Helper: create a mock Request with a proper headers mock."""
        request = MagicMock()
        mock_headers = MagicMock()
        mock_headers.get = lambda key, default=None: headers_map.get(key, default)
        request.headers = mock_headers
        return request

    def test_forwarded_for_uses_first_ip(self):
        """get_client_ip extracts the first IP from X-Forwarded-For."""
        from app.core.rate_limit import get_client_ip

        request = self._make_request({
            "x-real-ip": None,
            "x-forwarded-for": "1.2.3.4, 10.0.0.1, 192.168.1.1",
        })
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        result = get_client_ip(request)
        assert result == "1.2.3.4"

    def test_forwarded_for_single_ip(self):
        """get_client_ip handles single IP in X-Forwarded-For."""
        from app.core.rate_limit import get_client_ip

        request = self._make_request({
            "x-real-ip": None,
            "x-forwarded-for": "203.0.113.50",
        })
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        result = get_client_ip(request)
        assert result == "203.0.113.50"

    def test_real_ip_preferred_over_forwarded_for(self):
        """get_client_ip prefers X-Real-IP over X-Forwarded-For."""
        from app.core.rate_limit import get_client_ip

        request = self._make_request({
            "x-real-ip": "5.6.7.8",
            "x-forwarded-for": "1.2.3.4, 10.0.0.1",
        })
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        result = get_client_ip(request)
        assert result == "5.6.7.8"

    def test_falls_back_to_client_host(self):
        """get_client_ip falls back to request.client.host."""
        from app.core.rate_limit import get_client_ip

        request = self._make_request({})
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        result = get_client_ip(request)
        assert result == "192.168.1.100"

    def test_invalid_forwarded_for_falls_through(self):
        """get_client_ip skips invalid X-Forwarded-For values."""
        from app.core.rate_limit import get_client_ip

        request = self._make_request({
            "x-real-ip": None,
            "x-forwarded-for": "not-an-ip, also-not",
        })
        request.client = MagicMock()
        request.client.host = "10.0.0.1"

        result = get_client_ip(request)
        assert result == "10.0.0.1"


# ── M-04: apply_for_membership rate limiting ───────────────────────────

_EP = "app.api.v1.endpoints.applications"


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


_VALID_APPLY_BODY = {
    "username": "newuser",
    "password": "Passw0rd!",
    "display_name": "New User",
    "description": "I'd like to join the community.",
}


class TestApplyMembershipRateLimit:
    """M-04: apply_for_membership must have rate limiting."""

    @pytest.mark.anyio
    async def test_apply_rate_limited(self, client):
        """POST /users/apply-member returns 429 when rate limit exceeded."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with patch(
                f"{_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=_VALID_APPLY_BODY,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_apply_within_rate_limit(self, client):
        """POST /users/apply-member succeeds when within rate limit."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with (
                patch(
                    f"{_EP}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(f"{_EP}.create_application", new_callable=AsyncMock),
            ):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=_VALID_APPLY_BODY,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


# ── L-01: destroy_session JTI ownership ────────────────────────────────


class TestDestroySessionJTIOwnership:
    """L-01: destroy_session must verify JTI belongs to requesting user."""

    @pytest.mark.anyio
    async def test_destroy_session_matching_jti(self, mock_redis):
        """destroy_session deletes session when JTI matches."""
        from app.services.auth import destroy_session

        jti = "correct-jti-value"
        mock_redis.get = AsyncMock(return_value=jti)

        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await destroy_session("user-1", "MEMBER", jti)

        mock_redis.delete.assert_called_once()
        # Blacklist key should be set
        assert mock_redis.set.called

    @pytest.mark.anyio
    async def test_destroy_session_mismatched_jti(self, mock_redis):
        """destroy_session does NOT delete session when JTI does not match."""
        from app.services.auth import destroy_session

        mock_redis.get = AsyncMock(return_value="other-jti-value")

        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await destroy_session("user-1", "MEMBER", "attacker-jti")

        # Should NOT delete the session key
        mock_redis.delete.assert_not_called()
        # Should NOT blacklist the JTI
        mock_redis.set.assert_not_called()

    @pytest.mark.anyio
    async def test_destroy_session_no_existing_session(self, mock_redis):
        """destroy_session proceeds when no session exists (Redis returns None)."""
        from app.services.auth import destroy_session

        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.services.auth.get_redis", return_value=mock_redis):
            await destroy_session("user-1", "MEMBER", "some-jti")

        # Should still delete (idempotent cleanup) and blacklist
        mock_redis.delete.assert_called_once()
        assert mock_redis.set.called


# ── L-03: invite_code max_length ───────────────────────────────────────


class TestInviteCodeMaxLength:
    """L-03: invite_code field must have max_length."""

    def test_invite_code_max_length_enforced(self):
        """CreateAccountRequest rejects invite_code longer than 64 chars."""
        from pydantic import ValidationError

        from app.schemas.user import CreateAccountRequest

        with pytest.raises(ValidationError):
            CreateAccountRequest(
                username="testuser",
                password="Passw0rd!",
                display_name="Test",
                invite_code="A" * 65,
                captcha_id="cap",
                captcha_code="ABCD",
            )

    def test_invite_code_valid_length_accepted(self):
        """CreateAccountRequest accepts invite_code within 64 chars."""
        from app.schemas.user import CreateAccountRequest

        req = CreateAccountRequest(
            username="testuser",
            password="Passw0rd!",
            display_name="Test",
            invite_code="INV-" + "A" * 16,
            captcha_id="cap",
            captcha_code="ABCD",
        )
        assert len(req.invite_code) <= 64


# ── L-06: File cache-control ──────────────────────────────────────────


class TestFileCacheControl:
    """L-06: serve_file must not use immutable 1-year cache."""

    def test_cache_control_not_immutable(self):
        """Cache-Control header value must not contain 'immutable'."""
        import inspect

        from app.api.v1.endpoints import files

        source = inspect.getsource(files.serve_file)
        # Check the actual header value assignment (not comments)
        assert '"public, max-age=86400, must-revalidate"' in source
        assert '"public, max-age=31536000, immutable"' not in source


# ── L-11: Presigned URL filename escaping ──────────────────────────────


class TestPresignedURLFilenameEscaping:
    """L-11: generate_presigned_url must escape quotes in filename."""

    def test_filename_with_quotes_escaped(self):
        """Quotes in filename are escaped in Content-Disposition."""
        from unittest.mock import MagicMock

        from app.core import storage

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://example.com/file"

        original_get = storage.get_storage
        original_presign = storage._s3_presign_client

        try:
            storage._s3_presign_client = None
            storage._s3_client = mock_client

            storage.generate_presigned_url("key/file.pdf", filename='my"evil"file.pdf')

            call_args = mock_client.generate_presigned_url.call_args
            params = call_args[1]["Params"] if "Params" in call_args[1] else call_args[0][1]
            disposition = params["ResponseContentDisposition"]
            # The quotes should be escaped
            assert '\\"' in disposition or "evil" in disposition
            # No unescaped internal quotes that could break the header
            # The format is: attachment; filename="escaped_name"
            # Internal quotes must be backslash-escaped
            inner = disposition.split('filename="', 1)[1].rsplit('"', 1)[0]
            assert '"' not in inner.replace('\\"', "")
        finally:
            storage._s3_client = None
            storage._s3_presign_client = original_presign

    def test_filename_without_quotes_unchanged(self):
        """Normal filename without quotes is not altered."""
        from unittest.mock import MagicMock

        from app.core import storage

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://example.com/file"

        original_presign = storage._s3_presign_client

        try:
            storage._s3_presign_client = None
            storage._s3_client = mock_client

            storage.generate_presigned_url("key/file.pdf", filename="normal_file.pdf")

            call_args = mock_client.generate_presigned_url.call_args
            params = call_args[1]["Params"] if "Params" in call_args[1] else call_args[0][1]
            disposition = params["ResponseContentDisposition"]
            assert 'filename="normal_file.pdf"' in disposition
        finally:
            storage._s3_client = None
            storage._s3_presign_client = original_presign


# ── L-14: display_name min_length ──────────────────────────────────────


class TestDisplayNameMinLength:
    """L-14: display_name in UserUpdateRequest must reject empty string."""

    def test_empty_display_name_rejected(self):
        """UserUpdateRequest rejects empty string for display_name."""
        from pydantic import ValidationError

        from app.schemas.user import UserUpdateRequest

        with pytest.raises(ValidationError):
            UserUpdateRequest(display_name="")

    def test_none_display_name_accepted(self):
        """UserUpdateRequest accepts None (no update) for display_name."""
        from app.schemas.user import UserUpdateRequest

        req = UserUpdateRequest(display_name=None)
        assert req.display_name is None

    def test_valid_display_name_accepted(self):
        """UserUpdateRequest accepts non-empty display_name."""
        from app.schemas.user import UserUpdateRequest

        req = UserUpdateRequest(display_name="Alice")
        assert req.display_name == "Alice"


# ── L-15: Audit UUID validation ────────────────────────────────────────


class TestAuditUUIDValidation:
    """L-15: list_audit_logs must return 422 for invalid UUID, not 500."""

    @pytest.mark.anyio
    async def test_invalid_uuid_raises_app_error(self):
        """list_audit_logs raises AppError for invalid UUID filter."""
        from app.core.errors import AppError
        from app.services.audit import list_audit_logs

        with pytest.raises(AppError) as exc_info:
            await list_audit_logs(user_id_filter="not-a-valid-uuid")

        assert exc_info.value.status_code == 422

    @pytest.mark.anyio
    async def test_valid_uuid_passes_through(self):
        """list_audit_logs does not raise for valid UUID filter."""
        from app.services.audit import list_audit_logs

        valid_uuid = str(uuid.uuid4())

        with patch(
            "app.services.audit.audit_repo.find_many",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            logs, total = await list_audit_logs(user_id_filter=valid_uuid)

        assert logs == []
        assert total == 0

    @pytest.mark.anyio
    async def test_none_uuid_filter_works(self):
        """list_audit_logs works with no user_id filter."""
        from app.services.audit import list_audit_logs

        with patch(
            "app.services.audit.audit_repo.find_many",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            logs, total = await list_audit_logs(user_id_filter=None)

        assert logs == []
        assert total == 0
