"""Tests for invite code fixes: guest consumption, repo hardening, model consistency."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import make_user_dict

_EP = "app.api.v1.endpoints.auth"
_REPO = "app.repositories.auth_repo"
_IC_REPO = "app.repositories.invite_code_repo"
_SVC = "app.services.auth"


# ── #1  Guest login consumes invite code ──


class TestGuestLoginConsumesInviteCode:
    """Verify that guest login consumes the invite code (not just validates)."""

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.consume_invite_code", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.increment_guest_ip_counter", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.guest_login", new_callable=AsyncMock, return_value=("tok", "jti-g", 3600))
    async def test_guest_login_consumes_code(
        self, mock_gl, mock_ip, mock_consume, mock_captcha, mock_invite, mock_rl, client: AsyncClient
    ):
        """Guest login should call consume_invite_code after validation."""
        mock_invite.return_value = {"code": "INV-TEST", "id": uuid.uuid4()}

        resp = await client.post(
            "/api/v1/auth/guest/INV-TEST",
            json={"display_name": "Guest", "captcha_id": "c1", "captcha_code": "ABCD"},
        )
        assert resp.status_code == 200
        mock_consume.assert_called_once_with("INV-TEST")

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.consume_invite_code", new_callable=AsyncMock, return_value=False)
    async def test_guest_login_fails_when_consume_fails(
        self, mock_consume, mock_captcha, mock_invite, mock_rl, client: AsyncClient
    ):
        """Guest login returns 400 if invite code was consumed between validation and consumption."""
        mock_invite.return_value = {"code": "INV-RACE", "id": uuid.uuid4()}

        resp = await client.post(
            "/api/v1/auth/guest/INV-RACE",
            json={"display_name": "Guest", "captcha_id": "c1", "captcha_code": "ABCD"},
        )
        assert resp.status_code == 400
        assert "invite code" in resp.json()["detail"]["message"].lower()

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock, return_value=None)
    async def test_guest_login_rejects_invalid_code(
        self, mock_invite, mock_rl, client: AsyncClient
    ):
        """Guest login returns 404 for invalid invite code (unchanged behaviour)."""
        resp = await client.post(
            "/api/v1/auth/guest/BAD-CODE",
            json={"display_name": "Guest", "captcha_id": "c1", "captcha_code": "ABCD"},
        )
        assert resp.status_code == 404


# ── #3  find_invite_code no longer uses SELECT * ──


class TestFindInviteCodeColumns:
    """Ensure find_invite_code returns explicit columns, not SELECT *."""

    @pytest.mark.asyncio
    async def test_find_invite_code_uses_explicit_columns(self):
        """Repo should reference _INVITE_CODE_COLUMNS constant."""
        from app.repositories import auth_repo

        assert hasattr(auth_repo, "_INVITE_CODE_COLUMNS")
        cols = auth_repo._INVITE_CODE_COLUMNS
        assert "id" in cols
        assert "code" in cols
        assert "created_by" in cols
        assert "expires_at" in cols
        assert "consumed_at" in cols
        assert "consumed_by" in cols
        assert "*" not in cols


# ── #4  expires_at IS NULL removed from invite_code_repo ──


class TestExpiresAtConsistency:
    """Verify that invite_code_repo no longer contains 'expires_at IS NULL' checks."""

    def test_no_null_expires_at_in_repo(self):
        import inspect

        from app.repositories import invite_code_repo

        source = inspect.getsource(invite_code_repo)
        assert "expires_at IS NULL" not in source


# ── #5  consume_invite_code is no longer dead code ──


class TestConsumeInviteCodeSafety:
    """Verify consume_invite_code has safe WHERE clause and optional user_id."""

    def test_consume_accepts_none_user_id(self):
        """Repo consume_invite_code should accept user_id=None for guest usage."""
        import inspect

        from app.repositories.auth_repo import consume_invite_code

        sig = inspect.signature(consume_invite_code)
        param = sig.parameters["user_id"]
        # Default should be None
        assert param.default is None

    def test_consume_returns_bool(self):
        """consume_invite_code should return bool, not None."""
        import inspect

        from app.repositories.auth_repo import consume_invite_code

        sig = inspect.signature(consume_invite_code)
        annotation = sig.return_annotation
        # The return type should indicate bool (via coroutine)
        source = inspect.getsource(consume_invite_code)
        assert '-> bool' in source or 'bool' in str(annotation)

    def test_consume_has_safe_where_clause(self):
        """UPDATE should include consumed_at IS NULL AND expires_at > NOW()."""
        import inspect

        from app.repositories import auth_repo

        source = inspect.getsource(auth_repo.consume_invite_code)
        assert "consumed_at IS NULL" in source
        assert "expires_at > NOW()" in source


# ── #6  Verify rate limit is tightened ──


class TestInviteVerifyRateLimit:
    """Verify the invite verify rate limit was tightened."""

    def test_verify_rate_limit_value(self):
        from app.core.constants import RATE_LIMIT_INVITE_VERIFY

        max_requests, window = RATE_LIMIT_INVITE_VERIFY
        assert max_requests <= 10, "Invite verify rate limit should be 10 or lower per window"
        assert window == 60


# ── #7  Model has consumed_at and consumed_by ──


class TestInviteCodeModel:
    """Verify the ORM model includes consumed_at and consumed_by."""

    def test_model_has_consumed_fields(self):
        from app.models.invite_code import InviteCode

        # Check that the class has the mapped columns
        mapper = InviteCode.__table__.columns
        col_names = [c.name for c in mapper]
        assert "consumed_at" in col_names
        assert "consumed_by" in col_names

    def test_consumed_fields_are_nullable(self):
        from app.models.invite_code import InviteCode

        columns = {c.name: c for c in InviteCode.__table__.columns}
        assert columns["consumed_at"].nullable is True
        assert columns["consumed_by"].nullable is True


# ── Service layer: consume_invite_code with optional user_id ──


class TestConsumeInviteCodeService:
    @patch(f"{_REPO}.consume_invite_code", new_callable=AsyncMock, return_value=True)
    async def test_consume_with_user_id(self, mock_repo):
        from app.services.auth import consume_invite_code

        result = await consume_invite_code("INV-ABC", user_id="550e8400-e29b-41d4-a716-446655440000")
        assert result is True
        mock_repo.assert_called_once()
        args = mock_repo.call_args
        assert args[0][1] == uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

    @patch(f"{_REPO}.consume_invite_code", new_callable=AsyncMock, return_value=True)
    async def test_consume_without_user_id_for_guest(self, mock_repo):
        from app.services.auth import consume_invite_code

        result = await consume_invite_code("INV-GUEST")
        assert result is True
        mock_repo.assert_called_once()
        args = mock_repo.call_args
        assert args[0][1] is None  # user_id should be None

    @patch(f"{_REPO}.consume_invite_code", new_callable=AsyncMock, return_value=False)
    async def test_consume_returns_false_when_already_consumed(self, mock_repo):
        from app.services.auth import consume_invite_code

        result = await consume_invite_code("INV-USED")
        assert result is False
