"""Tests for Phase 3 medium-priority validation fixes (M-30 through M-42)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.errors import AppError

_ADMIN_EP = "app.api.v1.endpoints.admin"


# ── M-38: PostSearchRequest.keywords bounded ──────────────────────────────────


class TestPostSearchRequestKeywords:
    """PostSearchRequest should enforce max_length=15 and per-keyword 50-char limit."""

    def test_keywords_over_15_rejected(self):
        from app.schemas.post import PostSearchRequest

        with pytest.raises(ValidationError) as exc_info:
            PostSearchRequest(keywords=["kw"] * 16)
        errors = exc_info.value.errors()
        assert any("too_long" in str(e) for e in errors)

    def test_keywords_at_15_accepted(self):
        from app.schemas.post import PostSearchRequest

        req = PostSearchRequest(keywords=["kw"] * 15)
        assert len(req.keywords) == 15

    def test_keywords_none_accepted(self):
        from app.schemas.post import PostSearchRequest

        req = PostSearchRequest(keywords=None)
        assert req.keywords is None

    def test_single_keyword_over_50_chars_rejected(self):
        from app.schemas.post import PostSearchRequest

        long_kw = "a" * 51
        with pytest.raises(ValidationError) as exc_info:
            PostSearchRequest(keywords=[long_kw])
        assert "50 characters" in str(exc_info.value)

    def test_single_keyword_at_50_chars_accepted(self):
        from app.schemas.post import PostSearchRequest

        kw = "a" * 50
        req = PostSearchRequest(keywords=[kw])
        assert req.keywords == [kw]


# ── M-38: PostSearchRequest.category_id UUID pattern ──────────────────────────


class TestPostSearchRequestCategoryId:
    """PostSearchRequest.category_id should enforce UUID pattern."""

    def test_valid_uuid_accepted(self):
        from app.schemas.post import PostSearchRequest

        uid = str(uuid.uuid4())
        req = PostSearchRequest(category_id=uid)
        assert req.category_id == uid

    def test_invalid_category_id_rejected(self):
        from app.schemas.post import PostSearchRequest

        with pytest.raises(ValidationError):
            PostSearchRequest(category_id="not-a-uuid")


# ── M-39: PostUpdateRequest.category_id UUID pattern ─────────────────────────


class TestPostUpdateRequestCategoryId:
    """PostUpdateRequest.category_id should enforce UUID pattern."""

    def test_valid_uuid_accepted(self):
        from app.schemas.post import PostUpdateRequest

        uid = str(uuid.uuid4())
        req = PostUpdateRequest(category_id=uid, version=1)
        assert req.category_id == uid

    def test_invalid_category_id_rejected(self):
        from app.schemas.post import PostUpdateRequest

        with pytest.raises(ValidationError):
            PostUpdateRequest(category_id="not-a-uuid", version=1)


# ── M-39: CoAuthorInviteRequest.user_id UUID validation ───────────────────────


class TestCoAuthorInviteRequestUUID:
    """CoAuthorInviteRequest.user_id should reject non-UUID strings."""

    def test_valid_uuid_accepted(self):
        from app.schemas.co_author import CoAuthorInviteRequest

        uid = str(uuid.uuid4())
        req = CoAuthorInviteRequest(user_id=uid)
        assert req.user_id == uid

    def test_non_uuid_rejected(self):
        from app.schemas.co_author import CoAuthorInviteRequest

        with pytest.raises(ValidationError):
            CoAuthorInviteRequest(user_id="not-a-uuid")

    def test_uppercase_uuid_rejected(self):
        """UUID pattern requires lowercase hex digits."""
        from app.schemas.co_author import CoAuthorInviteRequest

        uid = str(uuid.uuid4()).upper()
        with pytest.raises(ValidationError):
            CoAuthorInviteRequest(user_id=uid)

    def test_empty_string_rejected(self):
        from app.schemas.co_author import CoAuthorInviteRequest

        with pytest.raises(ValidationError):
            CoAuthorInviteRequest(user_id="")


# ── M-39: DismissRequest.user_id UUID validation ─────────────────────────────


class TestDismissRequestUUID:
    """DismissRequest.user_id should reject non-UUID strings."""

    def test_valid_uuid_accepted(self):
        from app.schemas.recommendation import DismissRequest

        uid = str(uuid.uuid4())
        req = DismissRequest(user_id=uid)
        assert req.user_id == uid

    def test_non_uuid_rejected(self):
        from app.schemas.recommendation import DismissRequest

        with pytest.raises(ValidationError):
            DismissRequest(user_id="injection; DROP TABLE users;")


# ── M-40: invite-codes status_filter enum validation ──────────────────────────


def _override_auth(role="ADMIN", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestInviteCodeStatusFilter:
    """GET /admin/invite-codes?status=... should reject invalid values."""

    @pytest.mark.anyio
    async def test_valid_status_active_accepted(self, client):
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_ADMIN_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/admin/invite-codes?status=active",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_valid_status_consumed_accepted(self, client):
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_ADMIN_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/admin/invite-codes?status=consumed",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_valid_status_expired_accepted(self, client):
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_ADMIN_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/admin/invite-codes?status=expired",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_invalid_status_rejected(self, client):
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_ADMIN_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/admin/invite-codes?status=INVALID",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sql_injection_status_rejected(self, client):
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_ADMIN_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/admin/invite-codes?status=active' OR '1'='1",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_no_status_filter_accepted(self, client):
        """No status filter should return all codes."""
        try:
            _override_auth("ADMIN")
            with patch(
                f"{_ADMIN_EP}.list_invite_codes",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(
                    "/api/v1/admin/invite-codes",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


# ── M-42: Legacy Office Formats Rejected in DM ───────────────────────────────


class TestDMLegacyOfficeFormats:
    """DM should reject legacy .doc/.xls/.ppt files (macro risk)."""

    def test_doc_rejected(self):
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("document.doc", b"\xd0\xcf\x11\xe0binary data")
        assert exc.value.status_code == 400

    def test_xls_rejected(self):
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("spreadsheet.xls", b"\xd0\xcf\x11\xe0binary data")
        assert exc.value.status_code == 400

    def test_ppt_rejected(self):
        from app.services.dm import _validate_dm_file

        with pytest.raises(AppError) as exc:
            _validate_dm_file("presentation.ppt", b"\xd0\xcf\x11\xe0binary data")
        assert exc.value.status_code == 400

    def test_docx_still_accepted(self):
        """Modern .docx format (ZIP-based) should still be allowed."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("document.docx", b"PK\x03\x04rest of data")

    def test_xlsx_still_accepted(self):
        """Modern .xlsx format (ZIP-based) should still be allowed."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("spreadsheet.xlsx", b"PK\x03\x04rest of data")

    def test_pptx_still_accepted(self):
        """Modern .pptx format (ZIP-based) should still be allowed."""
        from app.services.dm import _validate_dm_file

        _validate_dm_file("presentation.pptx", b"PK\x03\x04rest of data")
