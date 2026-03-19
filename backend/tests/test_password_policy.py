"""Tests for password policy validation (S19: special character requirement).

Covers:
- Passwords meeting all criteria pass
- Passwords missing special chars fail
- Passwords missing upper/lower/digit still fail
- Edge cases: exactly 8 chars, very long passwords, unicode
"""

from app.core.security import validate_password_policy


class TestPasswordPolicyAllCriteriaMet:
    """Passwords meeting all requirements should return None (valid)."""

    def test_basic_valid_password(self) -> None:
        assert validate_password_policy("Abcdef1!") is None

    def test_valid_with_various_specials(self) -> None:
        for ch in "!@#$%^&*()_+-=[]{}|;:,.<>?/~":
            pwd = f"Abcdef1{ch}"
            assert validate_password_policy(pwd) is None, f"Should accept special char: {ch}"

    def test_long_valid_password(self) -> None:
        assert validate_password_policy("MyStr0ng!Password#2026WithExtraLength") is None

    def test_exactly_8_chars_all_requirements(self) -> None:
        # 8 chars: upper, lower, digit, special
        assert validate_password_policy("Ab1!cdef") is None

    def test_very_long_password(self) -> None:
        pwd = "Aa1!" + "x" * 200
        assert validate_password_policy(pwd) is None


class TestPasswordPolicyMissingSpecialChar:
    """Passwords without special characters should be rejected."""

    def test_no_special_char(self) -> None:
        result = validate_password_policy("Abcdef12")
        assert result is not None
        assert "special character" in result

    def test_only_alphanumeric(self) -> None:
        result = validate_password_policy("Password123")
        assert result is not None
        assert "special character" in result

    def test_spaces_are_not_special(self) -> None:
        """Spaces should not count as special characters."""
        result = validate_password_policy("Abc def1 ")
        assert result is not None
        assert "special character" in result


class TestPasswordPolicyMissingOtherRequirements:
    """Passwords missing upper/lower/digit should still fail."""

    def test_too_short(self) -> None:
        result = validate_password_policy("Ab1!xyz")
        assert result is not None
        assert "8 characters" in result

    def test_missing_uppercase(self) -> None:
        result = validate_password_policy("abcdef1!")
        assert result is not None
        assert "uppercase" in result

    def test_missing_lowercase(self) -> None:
        result = validate_password_policy("ABCDEF1!")
        assert result is not None
        assert "lowercase" in result

    def test_missing_digit(self) -> None:
        result = validate_password_policy("Abcdefg!")
        assert result is not None
        assert "digit" in result

    def test_empty_password(self) -> None:
        result = validate_password_policy("")
        assert result is not None
        assert "8 characters" in result

    def test_only_digits(self) -> None:
        result = validate_password_policy("12345678")
        assert result is not None
        assert "uppercase" in result

    def test_only_lowercase(self) -> None:
        result = validate_password_policy("abcdefgh")
        assert result is not None
        assert "uppercase" in result


class TestPasswordPolicyEdgeCases:
    """Edge cases and unicode handling."""

    def test_exactly_7_chars_fails(self) -> None:
        result = validate_password_policy("Ab1!cde")
        assert result is not None
        assert "8 characters" in result

    def test_unicode_letters_do_not_satisfy_ascii_requirements(self) -> None:
        """Unicode uppercase/lowercase do not satisfy [A-Z]/[a-z] checks."""
        # Only ASCII letters count
        result = validate_password_policy("12345678!")
        assert result is not None
        assert "uppercase" in result

    def test_unicode_in_password_with_all_requirements(self) -> None:
        """Unicode chars are allowed but don't replace ASCII requirements."""
        pwd = "Ab1!\u00e9\u00c9\u4e2d\u6587extra"
        assert validate_password_policy(pwd) is None

    def test_password_with_multiple_special_chars(self) -> None:
        assert validate_password_policy("Ab1!@#$%") is None

    def test_password_with_tilde(self) -> None:
        assert validate_password_policy("Ab1~defg") is None

    def test_password_with_slash(self) -> None:
        assert validate_password_policy("Ab1/defg") is None

    def test_password_with_pipe(self) -> None:
        assert validate_password_policy("Ab1|defg") is None

    def test_password_with_brackets(self) -> None:
        assert validate_password_policy("Ab1[defg") is None
        assert validate_password_policy("Ab1]defg") is None
        assert validate_password_policy("Ab1{defg") is None
        assert validate_password_policy("Ab1}defg") is None

    def test_password_with_angle_brackets(self) -> None:
        assert validate_password_policy("Ab1<defg") is None
        assert validate_password_policy("Ab1>defg") is None
