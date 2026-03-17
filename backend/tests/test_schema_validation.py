"""Tests for schema-level role validation (Bug 1 + Bug 2)."""

import pytest
from pydantic import ValidationError

from app.schemas.user import AdminCreateAccountRequest, RoleUpdateRequest


class TestRoleUpdateRequestValidation:
    def test_valid_roles(self):
        for role in ["SUPER_ADMIN", "ADMIN", "MEMBER"]:
            req = RoleUpdateRequest(role=role)
            assert req.role == role

    def test_guest_rejected(self):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role="GUEST")

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role="INVALID")

    def test_empty_role_rejected(self):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role="")

    def test_lowercase_rejected(self):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role="admin")


class TestAdminCreateAccountRequestValidation:
    def test_valid_roles(self):
        for role in ["MEMBER", "ADMIN"]:
            req = AdminCreateAccountRequest(
                username="testuser",
                password="P@ssword1!",
                display_name="Test",
                role=role,
            )
            assert req.role == role

    def test_default_role_is_member(self):
        req = AdminCreateAccountRequest(
            username="testuser", password="P@ssword1!", display_name="Test"
        )
        assert req.role == "MEMBER"

    def test_super_admin_rejected(self):
        with pytest.raises(ValidationError):
            AdminCreateAccountRequest(
                username="testuser",
                password="P@ssword1!",
                display_name="Test",
                role="SUPER_ADMIN",
            )

    def test_guest_rejected(self):
        with pytest.raises(ValidationError):
            AdminCreateAccountRequest(
                username="testuser",
                password="P@ssword1!",
                display_name="Test",
                role="GUEST",
            )

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            AdminCreateAccountRequest(
                username="testuser",
                password="P@ssword1!",
                display_name="Test",
                role="INVALID",
            )
