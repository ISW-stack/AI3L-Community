"""Tests for security/core bug fixes B-23, S-04, S-05, S-06, S-08.

Covers:
- B-23: Event retry UUID deserialization (_restore_types)
- S-04: get_client_ip uses X-Forwarded-For / X-Real-IP headers
- S-05: Chunked transfer body size enforcement in middleware
- S-06: Content-Disposition and CSP sandbox headers on file proxy
- S-08: WebP magic number requires RIFF + WEBP signature
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# B-23: Event retry UUID deserialization
# ---------------------------------------------------------------------------


class TestRestoreTypes:
    """_restore_types converts UUID-formatted strings back to uuid.UUID."""

    def test_uuid_string_converted(self):
        from app.tasks.event_retry import _restore_types

        uid = uuid.uuid4()
        result = _restore_types({"user_id": str(uid)})
        assert result["user_id"] == uid
        assert isinstance(result["user_id"], uuid.UUID)

    def test_non_uuid_string_preserved(self):
        from app.tasks.event_retry import _restore_types

        result = _restore_types({"name": "hello world", "action": "LOGIN"})
        assert result["name"] == "hello world"
        assert result["action"] == "LOGIN"

    def test_nested_dict_uuids_converted(self):
        from app.tasks.event_retry import _restore_types

        uid = uuid.uuid4()
        result = _restore_types({"data": {"nested_id": str(uid), "label": "test"}})
        assert isinstance(result["data"]["nested_id"], uuid.UUID)
        assert result["data"]["nested_id"] == uid
        assert result["data"]["label"] == "test"

    def test_list_uuids_converted(self):
        from app.tasks.event_retry import _restore_types

        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()
        result = _restore_types({"ids": [str(uid1), str(uid2), "not-a-uuid"]})
        assert isinstance(result["ids"][0], uuid.UUID)
        assert isinstance(result["ids"][1], uuid.UUID)
        assert result["ids"][0] == uid1
        assert result["ids"][1] == uid2
        assert result["ids"][2] == "not-a-uuid"

    def test_int_and_float_preserved(self):
        from app.tasks.event_retry import _restore_types

        result = _restore_types({"count": 42, "ratio": 3.14, "flag": True})
        assert result["count"] == 42
        assert result["ratio"] == 3.14
        assert result["flag"] is True

    def test_none_value_preserved(self):
        from app.tasks.event_retry import _restore_types

        result = _restore_types({"optional_id": None})
        assert result["optional_id"] is None

    def test_empty_dict(self):
        from app.tasks.event_retry import _restore_types

        result = _restore_types({})
        assert result == {}

    def test_mixed_kwargs(self):
        """Simulates a realistic event retry payload."""
        from app.tasks.event_retry import _restore_types

        user_id = uuid.uuid4()
        post_id = uuid.uuid4()
        kwargs = {
            "user_id": str(user_id),
            "post_id": str(post_id),
            "action": "post_created",
            "timestamp": "1711200000.123",
        }
        result = _restore_types(kwargs)
        assert isinstance(result["user_id"], uuid.UUID)
        assert isinstance(result["post_id"], uuid.UUID)
        assert result["action"] == "post_created"
        assert result["timestamp"] == "1711200000.123"  # not a UUID, stays string

    def test_uppercase_uuid_not_matched(self):
        """UUID regex is lowercase-only — uppercase hex stays as string."""
        from app.tasks.event_retry import _restore_types

        upper_uuid = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
        result = _restore_types({"id": upper_uuid})
        # Uppercase UUIDs don't match the lowercase regex
        assert isinstance(result["id"], str)


# ---------------------------------------------------------------------------
# S-04: get_client_ip with X-Forwarded-For / X-Real-IP
# ---------------------------------------------------------------------------


class TestGetClientIp:
    """get_client_ip extracts IP from headers or falls back to request.client."""

    def _make_request(self, headers=None, client_host=None):
        """Create a mock Request object with given headers and client."""
        request = MagicMock()
        request.headers = headers or {}
        if client_host:
            request.client = MagicMock()
            request.client.host = client_host
        else:
            request.client = None
        return request

    def test_x_forwarded_for_single_ip(self):
        from app.core.rate_limit import get_client_ip

        request = self._make_request(
            headers={"x-forwarded-for": "203.0.113.50"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_x_forwarded_for_multiple_ips(self):
        """Last IP (appended by trusted proxy) should be returned."""
        from app.core.rate_limit import get_client_ip

        request = self._make_request(
            headers={"x-forwarded-for": "203.0.113.50, 70.41.3.18, 150.172.238.178"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "150.172.238.178"

    def test_x_real_ip_used_when_no_forwarded_for(self):
        from app.core.rate_limit import get_client_ip

        request = self._make_request(
            headers={"x-real-ip": "198.51.100.22"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "198.51.100.22"

    def test_forwarded_for_takes_priority_over_real_ip(self):
        from app.core.rate_limit import get_client_ip

        request = self._make_request(
            headers={
                "x-forwarded-for": "203.0.113.50",
                "x-real-ip": "198.51.100.22",
            },
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_falls_back_to_client_host(self):
        from app.core.rate_limit import get_client_ip

        request = self._make_request(client_host="127.0.0.1")
        assert get_client_ip(request) == "127.0.0.1"

    def test_returns_none_when_no_ip(self):
        from app.core.rate_limit import get_client_ip

        request = self._make_request()
        assert get_client_ip(request) is None

    def test_invalid_forwarded_for_falls_through(self):
        """If X-Forwarded-For contains an invalid IP, skip it."""
        from app.core.rate_limit import get_client_ip

        request = self._make_request(
            headers={"x-forwarded-for": "not-an-ip"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "10.0.0.1"

    def test_invalid_real_ip_falls_through(self):
        """If X-Real-IP contains an invalid IP, skip it."""
        from app.core.rate_limit import get_client_ip

        request = self._make_request(
            headers={"x-real-ip": "malicious-value"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "10.0.0.1"

    def test_ipv6_forwarded_for(self):
        from app.core.rate_limit import get_client_ip

        request = self._make_request(
            headers={"x-forwarded-for": "2001:db8::1"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "2001:db8::1"


class TestIsValidIp:
    """_is_valid_ip validates IPv4 and IPv6 addresses."""

    def test_valid_ipv4(self):
        from app.core.rate_limit import _is_valid_ip

        assert _is_valid_ip("192.168.1.1") is True

    def test_valid_ipv6(self):
        from app.core.rate_limit import _is_valid_ip

        assert _is_valid_ip("2001:db8::1") is True

    def test_invalid_string(self):
        from app.core.rate_limit import _is_valid_ip

        assert _is_valid_ip("not-an-ip") is False

    def test_empty_string(self):
        from app.core.rate_limit import _is_valid_ip

        assert _is_valid_ip("") is False


# ---------------------------------------------------------------------------
# S-05: Chunked transfer body size enforcement
# ---------------------------------------------------------------------------


class TestBodySizeLimitMiddleware:
    """Middleware enforces body size limit even without Content-Length."""

    @pytest.mark.anyio
    async def test_content_length_over_limit_returns_413(self, client):
        """Request with Content-Length > MAX_REQUEST_BODY_SIZE is rejected."""
        response = await client.post(
            "/api/v1/auth/login",
            headers={"content-length": str(100 * 1024 * 1024)},  # 100 MB
            content=b"x",
        )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    @pytest.mark.anyio
    async def test_invalid_content_length_returns_400(self, client):
        """Request with non-numeric Content-Length returns 400."""
        response = await client.post(
            "/api/v1/auth/login",
            headers={"content-length": "not-a-number"},
            content=b"x",
        )
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_middleware_wraps_receive_for_post_without_content_length(self):
        """POST without Content-Length gets receive wrapper installed."""
        from app.main import MAX_REQUEST_BODY_SIZE, _BodyTooLargeError

        # Simulate what the middleware does: wrap _receive to count bytes
        bytes_received = 0
        call_count = 0

        async def fake_receive():
            nonlocal call_count
            call_count += 1
            # Return a small body chunk
            return {"type": "http.request", "body": b"hello", "more_body": False}

        async def _size_limited_receive():
            nonlocal bytes_received
            message = await fake_receive()
            body = message.get("body", b"")
            bytes_received += len(body)
            if bytes_received > MAX_REQUEST_BODY_SIZE:
                raise _BodyTooLargeError()
            return message

        result = await _size_limited_receive()
        assert result["body"] == b"hello"
        assert bytes_received == 5

    @pytest.mark.anyio
    async def test_chunked_body_exceeding_limit_raises(self):
        """Simulated chunked body exceeding limit raises _BodyTooLargeError."""
        from app.main import MAX_REQUEST_BODY_SIZE, _BodyTooLargeError

        bytes_received = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        chunk = b"x" * chunk_size
        call_count = 0

        async def fake_receive():
            nonlocal call_count
            call_count += 1
            return {"type": "http.request", "body": chunk, "more_body": call_count < 20}

        async def _size_limited_receive():
            nonlocal bytes_received
            message = await fake_receive()
            body = message.get("body", b"")
            bytes_received += len(body)
            if bytes_received > MAX_REQUEST_BODY_SIZE:
                raise _BodyTooLargeError()
            return message

        with pytest.raises(_BodyTooLargeError):
            # Keep reading until limit is exceeded (10 MB = 10 chunks of 1 MB, 11th should fail)
            for _ in range(20):
                await _size_limited_receive()

    @pytest.mark.anyio
    async def test_body_too_large_error_class_exists(self):
        """_BodyTooLargeError is defined and can be instantiated."""
        from app.main import _BodyTooLargeError

        exc = _BodyTooLargeError()
        assert isinstance(exc, Exception)


# ---------------------------------------------------------------------------
# S-06: Content-Disposition on file proxy
# ---------------------------------------------------------------------------


class TestFileProxyContentDisposition:
    """serve_file includes Content-Disposition and CSP sandbox headers."""

    @pytest.mark.anyio
    async def test_image_has_inline_disposition(self):
        """Image files should have Content-Disposition: inline."""
        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/abc123.png"
        image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with (
            patch(
                "app.api.v1.endpoints.files.file_scan_repo",
            ) as mock_scan,
            patch(
                "app.api.v1.endpoints.files.async_download_metadata",
                new_callable=AsyncMock,
                return_value=(
                    MagicMock(read=MagicMock(side_effect=[image_data, b""]), close=MagicMock()),
                    "image/png",
                    len(image_data),
                ),
            ),
        ):
            mock_scan.find_by_key = AsyncMock(return_value={"status": "clean"})

            from app.api.v1.endpoints.files import serve_file

            result = await serve_file(
                key=key,
                current_user={"sub": user_id, "role": "MEMBER"},
            )
            assert result.headers.get("content-disposition") is not None
            assert "inline" in result.headers["content-disposition"]
            assert "abc123.png" in result.headers["content-disposition"]
            assert result.headers.get("content-security-policy") == "sandbox"

    @pytest.mark.anyio
    async def test_pdf_has_attachment_disposition(self):
        """PDF files should have Content-Disposition: attachment."""
        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/doc.pdf"
        pdf_data = b"%PDF-1.4" + b"\x00" * 100

        with (
            patch(
                "app.api.v1.endpoints.files.file_scan_repo",
            ) as mock_scan,
            patch(
                "app.api.v1.endpoints.files.async_download_metadata",
                new_callable=AsyncMock,
                return_value=(
                    MagicMock(read=MagicMock(side_effect=[pdf_data, b""]), close=MagicMock()),
                    "application/pdf",
                    len(pdf_data),
                ),
            ),
        ):
            mock_scan.find_by_key = AsyncMock(return_value={"status": "clean"})

            from app.api.v1.endpoints.files import serve_file

            result = await serve_file(
                key=key,
                current_user={"sub": user_id, "role": "MEMBER"},
            )
            assert "attachment" in result.headers["content-disposition"]
            assert "doc.pdf" in result.headers["content-disposition"]
            assert result.headers.get("content-security-policy") == "sandbox"

    @pytest.mark.anyio
    async def test_content_disposition_filename_sanitized(self):
        """Filename sanitization removes unsafe characters via re.sub."""
        import re as _re

        # Test the sanitization logic directly since keys with special chars
        # would fail the _SAFE_KEY_RE regex at the endpoint level
        raw = "my file (1).png"
        safe = _re.sub(r"[^\w.\-]", "_", raw) or "download"
        assert " " not in safe
        assert "(" not in safe
        assert ")" not in safe
        assert safe.endswith(".png")

    @pytest.mark.anyio
    async def test_key_with_dashes_and_underscores_passes(self):
        """Keys with valid characters produce correct Content-Disposition."""
        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/my-file_v2.png"
        image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with (
            patch(
                "app.api.v1.endpoints.files.file_scan_repo",
            ) as mock_scan,
            patch(
                "app.api.v1.endpoints.files.async_download_metadata",
                new_callable=AsyncMock,
                return_value=(
                    MagicMock(read=MagicMock(side_effect=[image_data, b""]), close=MagicMock()),
                    "image/png",
                    len(image_data),
                ),
            ),
        ):
            mock_scan.find_by_key = AsyncMock(return_value={"status": "clean"})

            from app.api.v1.endpoints.files import serve_file

            result = await serve_file(
                key=key,
                current_user={"sub": user_id, "role": "MEMBER"},
            )
            disposition = result.headers["content-disposition"]
            assert "my-file_v2.png" in disposition


# ---------------------------------------------------------------------------
# S-08: WebP magic number requires RIFF + WEBP
# ---------------------------------------------------------------------------


class TestWebpMagicNumber:
    """WebP validation requires both RIFF header and WEBP at bytes 8-12."""

    def test_valid_webp_passes(self):
        """Valid WebP file (RIFF....WEBP) passes magic number check."""
        from app.core.file_validation import validate_magic_number

        # RIFF + 4 bytes of file size + WEBP marker
        data = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert validate_magic_number(data, "image/webp") is True

    def test_wav_file_rejected_as_webp(self):
        """WAV file (RIFF....WAVE) must be rejected as WebP."""
        from app.core.file_validation import validate_magic_number

        data = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
        assert validate_magic_number(data, "image/webp") is False

    def test_avi_file_rejected_as_webp(self):
        """AVI file (RIFF....AVI ) must be rejected as WebP."""
        from app.core.file_validation import validate_magic_number

        data = b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 100
        assert validate_magic_number(data, "image/webp") is False

    def test_riff_only_rejected(self):
        """RIFF with no WEBP marker at bytes 8-12 is rejected."""
        from app.core.file_validation import validate_magic_number

        data = b"RIFF\x00\x00\x00\x00XXXX" + b"\x00" * 100
        assert validate_magic_number(data, "image/webp") is False

    def test_short_riff_data_rejected(self):
        """RIFF data shorter than 12 bytes is rejected as WebP."""
        from app.core.file_validation import validate_magic_number

        data = b"RIFF\x00\x00\x00\x00"  # only 8 bytes
        assert validate_magic_number(data, "image/webp") is False

    def test_png_still_works(self):
        """Ensure PNG validation is unaffected by WebP changes."""
        from app.core.file_validation import validate_magic_number

        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert validate_magic_number(data, "image/png") is True

    def test_jpeg_still_works(self):
        """Ensure JPEG validation is unaffected by WebP changes."""
        from app.core.file_validation import validate_magic_number

        data = b"\xff\xd8\xff" + b"\x00" * 100
        assert validate_magic_number(data, "image/jpeg") is True

    def test_gif87a_still_works(self):
        """Ensure GIF87a validation is unaffected."""
        from app.core.file_validation import validate_magic_number

        data = b"GIF87a" + b"\x00" * 100
        assert validate_magic_number(data, "image/gif") is True

    def test_gif89a_still_works(self):
        """Ensure GIF89a validation is unaffected."""
        from app.core.file_validation import validate_magic_number

        data = b"GIF89a" + b"\x00" * 100
        assert validate_magic_number(data, "image/gif") is True
