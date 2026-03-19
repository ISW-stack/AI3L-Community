"""Tests for app.core.logging_utils — PII masking utilities."""

import re

from app.core.logging_utils import hash_identifier, mask_pii


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
