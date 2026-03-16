"""Tests for get_optional_current_user exception handling (S21).

Covers:
- AppError (expected auth failure) is caught and returns None
- Generic exceptions (e.g. RuntimeError, ConnectionError) propagate
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.deps import get_optional_current_user
from app.core.errors import AppError, ErrorCode


class TestGetOptionalCurrentUserExceptionHandling:
    """S21: Only catch AppError, let infrastructure exceptions propagate."""

    @pytest.mark.anyio
    async def test_returns_none_on_app_error(self):
        """AppError (e.g. missing token) results in None, not an exception."""
        mock_request = AsyncMock()
        mock_request.cookies = {}  # No access_token cookie

        with patch(
            "app.core.deps.get_current_user",
            new_callable=AsyncMock,
            side_effect=AppError(ErrorCode.AUTH_001, 401, "Missing token."),
        ):
            result = await get_optional_current_user(mock_request, None)

        assert result is None

    @pytest.mark.anyio
    async def test_returns_none_on_expired_token_error(self):
        """AppError for expired/invalid token results in None."""
        mock_request = AsyncMock()

        with patch(
            "app.core.deps.get_current_user",
            new_callable=AsyncMock,
            side_effect=AppError(ErrorCode.AUTH_002, 401, "Session expired."),
        ):
            result = await get_optional_current_user(mock_request, None)

        assert result is None

    @pytest.mark.anyio
    async def test_returns_none_on_banned_user_error(self):
        """AppError for banned user results in None."""
        mock_request = AsyncMock()

        with patch(
            "app.core.deps.get_current_user",
            new_callable=AsyncMock,
            side_effect=AppError(ErrorCode.AUTH_004, 403, "Banned."),
        ):
            result = await get_optional_current_user(mock_request, None)

        assert result is None

    @pytest.mark.anyio
    async def test_propagates_runtime_error(self):
        """RuntimeError (infrastructure failure) is NOT caught."""
        mock_request = AsyncMock()

        with (
            patch(
                "app.core.deps.get_current_user",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB connection pool exhausted"),
            ),
            pytest.raises(RuntimeError, match="DB connection pool exhausted"),
        ):
            await get_optional_current_user(mock_request, None)

    @pytest.mark.anyio
    async def test_propagates_connection_error(self):
        """ConnectionError (Redis/DB down) is NOT caught."""
        mock_request = AsyncMock()

        with (
            patch(
                "app.core.deps.get_current_user",
                new_callable=AsyncMock,
                side_effect=ConnectionError("Redis connection refused"),
            ),
            pytest.raises(ConnectionError, match="Redis connection refused"),
        ):
            await get_optional_current_user(mock_request, None)

    @pytest.mark.anyio
    async def test_propagates_os_error(self):
        """OSError (low-level system failure) is NOT caught."""
        mock_request = AsyncMock()

        with (
            patch(
                "app.core.deps.get_current_user",
                new_callable=AsyncMock,
                side_effect=OSError("Disk full"),
            ),
            pytest.raises(OSError, match="Disk full"),
        ):
            await get_optional_current_user(mock_request, None)

    @pytest.mark.anyio
    async def test_propagates_value_error(self):
        """ValueError (unexpected coding error) is NOT caught."""
        mock_request = AsyncMock()

        with (
            patch(
                "app.core.deps.get_current_user",
                new_callable=AsyncMock,
                side_effect=ValueError("Invalid UUID format"),
            ),
            pytest.raises(ValueError, match="Invalid UUID format"),
        ):
            await get_optional_current_user(mock_request, None)

    @pytest.mark.anyio
    async def test_returns_user_on_success(self):
        """When auth succeeds, the user dict is returned."""
        mock_request = AsyncMock()
        expected_user = {"sub": "user-123", "role": "MEMBER", "jti": "jti-abc"}

        with patch(
            "app.core.deps.get_current_user",
            new_callable=AsyncMock,
            return_value=expected_user,
        ):
            result = await get_optional_current_user(mock_request, None)

        assert result == expected_user
