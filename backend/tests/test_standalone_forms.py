"""Tests for standalone forms (top-level, not attached to any SIG).

Covers: create, list, get detail, submit, converter None sig_id,
regression (SIG form still works), rate limiting, limit enforcement.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP = "app.api.v1.endpoints.forms"
_SVC = "app.services.form"
_REPO = "app.repositories.form_repo"


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


def _make_standalone_form(creator_id=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "sig_id": None,
        "title": "Standalone Survey",
        "description": "A standalone form",
        "banner_url": None,
        "deadline": None,
        "max_respondents": None,
        "questions": [{"id": "q1", "type": "text", "label": "Name", "required": True}],
        "is_schema_locked": False,
        "allow_non_members": True,
        "response_count": 0,
        "is_active": True,
        "created_by": creator_id or str(uuid.uuid4()),
        "created_by_name": "Test User",
        "created_at": now,
        "updated_at": now,
    }


def _make_sig_form(sig_id=None, creator_id=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "sig_id": sig_id or str(uuid.uuid4()),
        "title": "SIG Form",
        "description": "A SIG form",
        "banner_url": None,
        "deadline": None,
        "max_respondents": None,
        "questions": [{"id": "q1", "type": "text", "label": "Name", "required": True}],
        "is_schema_locked": False,
        "allow_non_members": False,
        "response_count": 0,
        "is_active": True,
        "created_by": creator_id or str(uuid.uuid4()),
        "created_by_name": "Test User",
        "created_at": now,
        "updated_at": now,
    }


class TestCreateStandaloneForm:
    @pytest.mark.anyio
    async def test_create_standalone_form_success(self, client):
        """POST /forms → 201 for authenticated MEMBER."""
        form = _make_standalone_form()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_form", new_callable=AsyncMock, return_value=form),
            ):
                resp = await client.post(
                    "/api/v1/forms",
                    json={
                        "title": "Standalone Survey",
                        "description": "A standalone form",
                        "questions": [
                            {"id": "q1", "type": "text", "label": "Name", "required": True}
                        ],
                    },
                )
                assert resp.status_code == 201
                data = resp.json()
                assert data["title"] == "Standalone Survey"
                assert data["sig_id"] is None
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_standalone_form_as_guest_forbidden(self, client):
        """POST /forms → 403 for GUEST role."""
        try:
            _override_auth("GUEST")
            resp = await client.post(
                "/api/v1/forms",
                json={
                    "title": "Guest Form",
                    "questions": [{"id": "q1", "type": "text", "label": "Name", "required": True}],
                },
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_standalone_form_limit_exceeded(self, client):
        """POST /forms → 400 when user has too many active standalone forms."""
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_form",
                    new_callable=AsyncMock,
                    side_effect=ValueError(
                        "Maximum active standalone forms per user (10) reached."
                    ),
                ),
            ):
                resp = await client.post(
                    "/api/v1/forms",
                    json={
                        "title": "Too Many Forms",
                        "questions": [
                            {"id": "q1", "type": "text", "label": "Name", "required": True}
                        ],
                    },
                )
                assert resp.status_code == 400
                assert "Maximum active standalone forms" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_standalone_form_rate_limited(self, client):
        """POST /forms → 429 when rate limit exceeded."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    "/api/v1/forms",
                    json={
                        "title": "Rate Limited",
                        "questions": [
                            {"id": "q1", "type": "text", "label": "Name", "required": True}
                        ],
                    },
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestListStandaloneForms:
    @pytest.mark.anyio
    async def test_list_standalone_forms_no_auth(self, client):
        """GET /forms → 200 without authentication."""
        form = _make_standalone_form()
        with (
            patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            patch(
                f"{_EP}.list_standalone_forms_svc",
                new_callable=AsyncMock,
                return_value=([form], 1),
            ),
        ):
            resp = await client.get("/api/v1/forms")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["forms"]) == 1
            assert data["forms"][0]["sig_id"] is None

    @pytest.mark.anyio
    async def test_list_standalone_forms_pagination(self, client):
        """GET /forms?page=2&page_size=1 → correct pagination."""
        form = _make_standalone_form()
        with (
            patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            patch(
                f"{_EP}.list_standalone_forms_svc",
                new_callable=AsyncMock,
                return_value=([form], 3),
            ) as mock_list,
        ):
            resp = await client.get("/api/v1/forms?page=2&page_size=1")
            assert resp.status_code == 200
            mock_list.assert_called_once_with(page=2, page_size=1)

    @pytest.mark.anyio
    async def test_list_standalone_forms_empty(self, client):
        """GET /forms → 200 with empty list when no standalone forms."""
        with (
            patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            patch(
                f"{_EP}.list_standalone_forms_svc",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
        ):
            resp = await client.get("/api/v1/forms")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["forms"] == []


class TestGetStandaloneFormDetail:
    @pytest.mark.anyio
    async def test_get_standalone_form_detail(self, client):
        """GET /forms/{form_id} → 200 for standalone form."""
        form_id = uuid.uuid4()
        form = _make_standalone_form()
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form):
                resp = await client.get(f"/api/v1/forms/{form_id}")
                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == str(form_id)
                assert data["sig_id"] is None
        finally:
            _clear_overrides()


class TestSubmitStandaloneForm:
    @pytest.mark.anyio
    async def test_submit_standalone_form(self, client):
        """POST /forms/{form_id}/submit → 201 for standalone form."""
        form_id = uuid.uuid4()
        result = {"id": str(uuid.uuid4()), "message": "Response submitted successfully."}

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.submit_response", new_callable=AsyncMock, return_value=result),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "John Doe"}},
                )
                assert resp.status_code == 201
                assert resp.json()["message"] == "Response submitted successfully."
        finally:
            _clear_overrides()


class TestStandaloneFormServiceLayer:
    """Test service-layer logic for standalone forms."""

    @pytest.mark.anyio
    async def test_create_form_standalone_enforces_limit(self):
        """create_form(sig_id=None) enforces per-user standalone limit."""
        from app.services.form import create_form

        user_id = str(uuid.uuid4())
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"cnt": 10})
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(ValueError, match="Maximum active standalone forms per user"):
                await create_form(
                    sig_id=None,
                    user_id=user_id,
                    title="Test",
                    description=None,
                    banner_url=None,
                    deadline=None,
                    max_respondents=None,
                    questions=[{"id": "q1", "type": "text", "label": "Name"}],
                )

    @pytest.mark.anyio
    async def test_create_form_standalone_forces_allow_non_members(self):
        """create_form(sig_id=None) forces allow_non_members=True."""
        from app.services.form import create_form

        user_id = str(uuid.uuid4())
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"cnt": 0})
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        now = datetime.now(timezone.utc)
        fake_row = {
            "id": uuid.uuid4(),
            "sig_id": None,
            "created_by": uuid.UUID(user_id),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": '[{"id": "q1", "type": "text", "label": "Name"}]',
            "is_schema_locked": False,
            "allow_non_members": True,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(
                f"{_SVC}.form_repo.insert",
                new_callable=AsyncMock,
                return_value={**fake_row, "creator_display_name": "Test User"},
            ) as mock_insert,
        ):
            await create_form(
                sig_id=None,
                user_id=user_id,
                title="Test",
                description=None,
                banner_url=None,
                deadline=None,
                max_respondents=None,
                questions=[{"id": "q1", "type": "text", "label": "Name"}],
                allow_non_members=False,  # Should be forced to True
            )
            # Verify insert was called with allow_non_members=True
            call_args = mock_insert.call_args
            assert call_args[0][1] is None  # sig_id is None
            assert call_args[0][9] is True  # allow_non_members forced True

    @pytest.mark.anyio
    async def test_submit_response_standalone_skips_sig_check(self):
        """submit_response() skips SIG membership check for standalone forms."""
        from app.services.form import submit_response

        user_id = str(uuid.uuid4())
        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        form_row = {
            "id": form_id,
            "sig_id": None,  # Standalone
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": '[{"id": "q1", "type": "text", "label": "Name", "required": true}]',
            "is_schema_locked": False,
            "allow_non_members": True,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(
                f"{_SVC}.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 0),
            ),
            patch(
                f"{_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=form_row,
            ),
            patch(
                f"{_SVC}.form_repo.check_duplicate_response",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                f"{_SVC}.form_repo.insert_response",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                f"{_SVC}.form_repo.lock_schema",
                new_callable=AsyncMock,
            ),
            patch(f"{_SVC}._validate_file_sizes", new_callable=AsyncMock),
        ):
            result = await submit_response(
                form_id=form_id,
                user_id=user_id,
                answers={"q1": "Test Answer"},
            )
            assert result["message"] == "Response submitted successfully."

    @pytest.mark.anyio
    async def test_list_standalone_forms_service(self):
        """list_standalone_forms returns converted rows and total."""
        from app.services.form import list_standalone_forms

        now = datetime.now(timezone.utc)
        # Use a plain dict-like object that supports both [] and .get()
        fake_row = {
            "id": uuid.uuid4(),
            "sig_id": None,
            "created_by": uuid.uuid4(),
            "title": "Form 1",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "is_schema_locked": False,
            "allow_non_members": True,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "total_count": 1,
            "creator_display_name": "User",
            "response_count": 0,
        }
        fake_rows = [fake_row]

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(
                f"{_SVC}.form_repo.find_standalone",
                new_callable=AsyncMock,
                return_value=fake_rows,
            ),
        ):
            forms, total = await list_standalone_forms(page=1, page_size=20)
            assert total == 1
            assert len(forms) == 1
            assert forms[0]["sig_id"] is None

    @pytest.mark.anyio
    async def test_list_standalone_forms_includes_response_count(self):
        """list_standalone_forms passes response_count from repo to converter."""
        from app.services.form import list_standalone_forms

        now = datetime.now(timezone.utc)
        fake_row = {
            "id": uuid.uuid4(),
            "sig_id": None,
            "created_by": uuid.uuid4(),
            "title": "Popular Form",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "is_schema_locked": False,
            "allow_non_members": True,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "total_count": 1,
            "creator_display_name": "User",
            "response_count": 42,
        }
        fake_rows = [fake_row]

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
            patch(
                f"{_SVC}.form_repo.find_standalone",
                new_callable=AsyncMock,
                return_value=fake_rows,
            ),
        ):
            forms, total = await list_standalone_forms(page=1, page_size=20)
            assert total == 1
            assert forms[0]["response_count"] == 42


class TestConverterNoneSigId:
    def test_converter_handles_none_sig_id(self):
        """row_to_form handles sig_id=None correctly."""
        from app.converters.form_converter import row_to_form

        now = datetime.now(timezone.utc)
        row = {
            "id": uuid.uuid4(),
            "sig_id": None,
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "is_schema_locked": False,
            "allow_non_members": True,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "User",
        }
        result = row_to_form(row, 0)
        assert result["sig_id"] is None
        assert result["title"] == "Test"

    def test_converter_handles_present_sig_id(self):
        """row_to_form handles present sig_id correctly (regression)."""
        from app.converters.form_converter import row_to_form

        now = datetime.now(timezone.utc)
        sig_id = uuid.uuid4()
        row = {
            "id": uuid.uuid4(),
            "sig_id": sig_id,
            "created_by": uuid.uuid4(),
            "title": "SIG Form",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "User",
        }
        result = row_to_form(row, 0)
        assert result["sig_id"] == str(sig_id)


class TestRegressionSigFormStillWorks:
    @pytest.mark.anyio
    async def test_create_sig_form_still_works(self, client):
        """POST /sigs/{sig_id}/forms → 201 (regression: SIG forms unaffected)."""
        sig_id = uuid.uuid4()
        form = _make_sig_form(sig_id=str(sig_id))

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_form", new_callable=AsyncMock, return_value=form),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/forms",
                    json={
                        "title": "SIG Form",
                        "questions": [
                            {"id": "q1", "type": "text", "label": "Name", "required": True}
                        ],
                    },
                )
                assert resp.status_code == 201
                assert resp.json()["sig_id"] == str(sig_id)
        finally:
            _clear_overrides()
