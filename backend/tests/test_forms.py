"""Tests for forms endpoints — create, list, get, update, delete, submit, export."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP = "app.api.v1.endpoints.forms"


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


def _make_form(sig_id=None, creator_id=None):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "sig_id": sig_id or str(uuid.uuid4()),
        "title": "Test Form",
        "description": "A test form",
        "banner_url": None,
        "deadline": None,
        "max_respondents": None,
        "questions": [{"id": "q1", "type": "text", "label": "Name", "required": True}],
        "is_schema_locked": False,
        "response_count": 0,
        "is_active": True,
        "created_by": creator_id or str(uuid.uuid4()),
        "created_by_name": "Test User",
        "created_at": now,
        "updated_at": now,
    }


class TestCreateForm:
    @pytest.mark.anyio
    async def test_create_form(self, client):
        """POST /sigs/{sig_id}/forms → 201."""
        sig_id = uuid.uuid4()
        form = _make_form(sig_id=str(sig_id))

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}._check_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_form", new_callable=AsyncMock, return_value=form),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/forms",
                    json={
                        "title": "Test Form",
                        "description": "A test form",
                        "questions": [
                            {"id": "q1", "type": "text", "label": "Name", "required": True}
                        ],
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["title"] == "Test Form"
        finally:
            _clear_overrides()


class TestListForms:
    @pytest.mark.anyio
    async def test_list_forms(self, client):
        """GET /sigs/{sig_id}/forms → 200."""
        sig_id = uuid.uuid4()
        form = _make_form(sig_id=str(sig_id))

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}._check_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(f"{_EP}.list_forms_by_sig", new_callable=AsyncMock, return_value=([form], 1)),
            ):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/forms",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()


class TestGetForm:
    @pytest.mark.anyio
    async def test_get_form(self, client):
        """GET /forms/{form_id} → 200."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}._check_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["id"] == str(form_id)
        finally:
            _clear_overrides()


class TestUpdateForm:
    @pytest.mark.anyio
    async def test_update_form(self, client):
        """PUT /forms/{form_id} → 200."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)
        form["title"] = "Updated Title"

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.update_form", new_callable=AsyncMock, return_value=form):
                resp = await client.put(
                    f"/api/v1/forms/{form_id}",
                    json={"title": "Updated Title"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["title"] == "Updated Title"
        finally:
            _clear_overrides()


class TestDeleteForm:
    @pytest.mark.anyio
    async def test_delete_form(self, client):
        """DELETE /forms/{form_id} → 204."""
        form_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.soft_delete_form", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()


class TestSubmitForm:
    @pytest.mark.anyio
    async def test_submit_form(self, client):
        """POST /forms/{form_id}/submit → 201."""
        form_id = uuid.uuid4()
        result = {"id": str(uuid.uuid4()), "message": "Response submitted successfully."}

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.submit_response", new_callable=AsyncMock, return_value=result):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "John Doe"}},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert "submitted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()


class TestExportForm:
    @pytest.mark.anyio
    async def test_export_form(self, client):
        """POST /forms/{form_id}/export → 202."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)

        mock_task = MagicMock()
        mock_task.id = "celery-task-123"

        # Mock the module-level import inside the function
        mock_export_module = MagicMock()
        mock_export_module.export_form_csv.delay.return_value = mock_task

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._check_sig_admin", new_callable=AsyncMock, return_value=True),
                patch.dict("sys.modules", {"app.tasks.form_export": mock_export_module}),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/export",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 202
                assert resp.json()["task_id"] == "celery-task-123"
        finally:
            _clear_overrides()
