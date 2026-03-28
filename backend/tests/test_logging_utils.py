"""Tests for app.core.logging_utils — PII masking and error sanitization utilities."""

import re

from app.core.logging_utils import hash_identifier, mask_pii, safe_error_detail


class TestMaskPii:
    """Tests for the mask_pii function."""

    def test_normal_string(self) -> None:
        assert mask_pii("Alice Smith") == "Ali***"

    def test_short_string_equal_to_keep(self) -> None:
        """Strings with length <= keep_chars should be fully masked."""
        assert mask_pii("AB") == "***"

    def test_short_string_exactly_keep(self) -> None:
        assert mask_pii("ABC") == "***"

    def test_empty_string(self) -> None:
        assert mask_pii("") == "***"

    def test_custom_keep_chars(self) -> None:
        assert mask_pii("INV-ABCD1234", 4) == "INV-***"

    def test_keep_chars_zero(self) -> None:
        """With keep_chars=0, even non-empty strings are fully masked."""
        assert mask_pii("hello", 0) == "***"

    def test_single_char_over_keep(self) -> None:
        """String of length 4 with keep_chars=3 shows first 3."""
        assert mask_pii("ABCD") == "ABC***"

    def test_unicode_string(self) -> None:
        result = mask_pii("张三丰大侠")
        assert result == "张三丰***"

    def test_email_address(self) -> None:
        result = mask_pii("user@example.com")
        assert result == "use***"

    def test_keep_chars_larger_than_string(self) -> None:
        """If keep_chars > len(value), mask entirely."""
        assert mask_pii("AB", 5) == "***"


class TestHashIdentifier:
    """Tests for the hash_identifier function."""

    def test_returns_12_char_hex(self) -> None:
        result = hash_identifier("user123")
        assert len(result) == 12
        assert re.fullmatch(r"[0-9a-f]{12}", result)

    def test_deterministic(self) -> None:
        """Same input always produces the same hash."""
        assert hash_identifier("test") == hash_identifier("test")

    def test_different_inputs_differ(self) -> None:
        assert hash_identifier("user1") != hash_identifier("user2")

    def test_empty_string(self) -> None:
        result = hash_identifier("")
        assert len(result) == 12
        assert re.fullmatch(r"[0-9a-f]{12}", result)


class TestSafeErrorDetail:
    """Tests for safe_error_detail — error message sanitization."""

    def test_normal_validation_message_passes_through(self) -> None:
        exc = ValueError("Title is required.")
        assert safe_error_detail(exc, "fallback") == "Title is required."

    def test_empty_message_returns_fallback(self) -> None:
        exc = ValueError("")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_long_message_returns_fallback(self) -> None:
        exc = ValueError("x" * 301)
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_sql_select_returns_fallback(self) -> None:
        exc = ValueError("SELECT id FROM users WHERE id = 1")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_file_path_returns_fallback(self) -> None:
        exc = ValueError("error in /app/services/form.py line 42")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_traceback_returns_fallback(self) -> None:
        exc = ValueError("Traceback (most recent call last):")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_asyncpg_error_returns_fallback(self) -> None:
        exc = ValueError("asyncpg.UniqueViolationError: duplicate key")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_connection_error_returns_fallback(self) -> None:
        exc = ValueError("ConnectionRefused: cannot connect to host")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_insert_sql_returns_fallback(self) -> None:
        exc = ValueError("INSERT INTO form_responses VALUES (...)")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_delete_from_sql_returns_fallback(self) -> None:
        exc = ValueError("DELETE FROM users WHERE id = 1")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_update_sql_returns_fallback(self) -> None:
        exc = ValueError("UPDATE users SET role = 'ADMIN' WHERE id = 1")
        assert safe_error_detail(exc, "fallback") == "fallback"

    def test_permission_error_passes_through(self) -> None:
        exc = PermissionError("Only SIG admins can delete this form.")
        assert safe_error_detail(exc, "fallback") == "Only SIG admins can delete this form."

    def test_safe_short_message(self) -> None:
        exc = ValueError("Invalid question type 'foo'.")
        assert safe_error_detail(exc, "fallback") == "Invalid question type 'foo'."

    def test_detail_hint_returns_fallback(self) -> None:
        exc = ValueError("DETAIL: Key (id)=(abc) already exists.")
        assert safe_error_detail(exc, "fallback") == "fallback"
