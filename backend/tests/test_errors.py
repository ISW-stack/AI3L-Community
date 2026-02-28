"""Tests for app.core.errors — ErrorCode enum and AppError format."""

from app.core.errors import AppError, ErrorCode


class TestErrorCodes:
    def test_error_codes_enum(self):
        """All 8 error codes must exist."""
        expected = ["AUTH_001", "AUTH_002", "AUTH_003", "AUTH_004", "SYS_409", "SYS_429", "FILE_001", "FORM_001"]
        actual = [e.value for e in ErrorCode]
        assert sorted(actual) == sorted(expected)

    def test_all_codes_are_strings(self):
        for code in ErrorCode:
            assert isinstance(code.value, str)


class TestAppError:
    def test_app_error_format(self):
        """Verify detail dict format: {"code": "...", "message": "..."}."""
        error = AppError(ErrorCode.AUTH_001, 401, "Token expired.")
        assert error.status_code == 401
        assert error.detail == {"code": "AUTH_001", "message": "Token expired."}

    def test_app_error_banned(self):
        error = AppError(ErrorCode.AUTH_004, 403, "Account is banned: spam")
        assert error.status_code == 403
        assert error.detail["code"] == "AUTH_004"
        assert "banned" in error.detail["message"]

    def test_app_error_rate_limit(self):
        error = AppError(ErrorCode.SYS_429, 429, "Too many requests.")
        assert error.status_code == 429
        assert error.detail["code"] == "SYS_429"
