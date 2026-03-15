"""Tests for forms endpoints — create, list, get, update, delete, submit, export.
Also covers update_form transaction safety.
"""

import uuid
from datetime import datetime, timezone
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EP = "app.api.v1.endpoints.forms"
_SVC = "app.services.form"


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


def _make_form(sig_id=None, creator_id=None, allow_non_members=False):
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
        "allow_non_members": allow_non_members,
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
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
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
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
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
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
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
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.update_form", new_callable=AsyncMock, return_value=form),
            ):
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
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.submit_response", new_callable=AsyncMock, return_value=result),
            ):
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

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch.dict("sys.modules", {"app.tasks.form_export": mock_export_module}),
                patch("app.core.redis.get_redis", return_value=mock_redis),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/export",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 202
                assert resp.json()["task_id"] == "celery-task-123"
                mock_redis.set.assert_awaited_once_with(
                    "task_owner:celery-task-123", mock.ANY, ex=86400
                )
        finally:
            _clear_overrides()


class TestSubmitFormMembership:
    @pytest.mark.anyio
    async def test_submit_non_member_denied(self, client):
        """POST /forms/{form_id}/submit → 403 when non-member."""
        form_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Only SIG members can submit this form."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "John Doe"}},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "SIG members" in resp.json()["detail"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_submit_non_member_allowed(self, client):
        """POST /forms/{form_id}/submit → 201 when allow_non_members is True."""
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
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert "submitted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()


class TestDeleteFormSigAdmin:
    @pytest.mark.anyio
    async def test_sig_admin_can_delete_others_form(self, client):
        """DELETE /forms/{form_id} by SIG admin (not platform admin) → 204."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator_id = str(uuid.uuid4())  # different person
        form = _make_form(creator_id=creator_id)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.soft_delete_form", new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.delete(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_admin_non_creator_forbidden(self, client):
        """DELETE /forms/{form_id} by non-admin, non-creator → 403."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator_id = str(uuid.uuid4())
        form = _make_form(creator_id=creator_id)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.soft_delete_form",
                    new_callable=AsyncMock,
                    side_effect=PermissionError(
                        "Only the form creator or admin can delete this form."
                    ),
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestUpdateFormTransaction:
    """Verify update_form wraps its read-then-update in a single transaction."""

    @pytest.mark.anyio
    async def test_update_form_uses_transaction(self, mock_pool, mock_conn):
        """update_form must wrap find_for_update → UPDATE inside conn.transaction()."""
        from app.services.form import update_form

        form_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": creator_id,
            "title": "Original Title",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        updated_row = dict(form_row)
        updated_row["title"] = "New Title"
        creator_row = {"display_name": "Test User"}

        # find_for_update → update fetchrow → creator fetchrow for update result
        mock_conn.fetchrow = AsyncMock(side_effect=[form_row, updated_row, creator_row])
        # count_responses inside form_repo.update
        mock_conn.fetchval = AsyncMock(return_value=0)

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            result = await update_form(
                form_id=form_id,
                user_id=str(creator_id),
                is_admin=False,
                title="New Title",
            )

        assert result is not None
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_update_form_not_found_uses_transaction(self, mock_pool, mock_conn):
        """update_form returns None for missing form but still enters transaction."""
        from app.services.form import update_form

        form_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            result = await update_form(
                form_id=form_id,
                user_id=str(uuid.uuid4()),
                is_admin=False,
                title="Whatever",
            )

        assert result is None
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_update_form_permission_error_uses_transaction(self, mock_pool, mock_conn):
        """update_form raises PermissionError for non-owner, inside a transaction."""
        from app.services.form import update_form

        form_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        other_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": creator_id,
            "title": "Title",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        mock_conn.fetchrow = AsyncMock(return_value=form_row)

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(PermissionError):
                await update_form(
                    form_id=form_id,
                    user_id=other_user_id,
                    is_admin=False,
                    title="Attempt",
                )

        mock_conn.transaction.assert_called_once()


# ──────────────────────────────────────────────────────────────────────
# NEW TESTS: Bug fix coverage
# ──────────────────────────────────────────────────────────────────────


class TestRateLimitKeyScope:
    """Bug 1.1 — rate limit key must include form_id."""

    @pytest.mark.anyio
    async def test_rate_limit_key_includes_form_id(self, client):
        """Submitting two different forms should NOT share rate limit."""
        form_id_a = uuid.uuid4()
        form_id_b = uuid.uuid4()
        result = {"id": str(uuid.uuid4()), "message": "Response submitted successfully."}

        try:
            _, uid = _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock) as mock_rl,
                patch(f"{_EP}.submit_response", new_callable=AsyncMock, return_value=result),
            ):
                mock_rl.return_value = True
                await client.post(
                    f"/api/v1/forms/{form_id_a}/submit",
                    json={"answers": {"q1": "A"}},
                    headers={"Authorization": "Bearer fake"},
                )
                await client.post(
                    f"/api/v1/forms/{form_id_b}/submit",
                    json={"answers": {"q1": "B"}},
                    headers={"Authorization": "Bearer fake"},
                )
                # Verify each call used a different key containing the form_id
                keys_used = [call.args[0] for call in mock_rl.call_args_list]
                assert str(form_id_a) in keys_used[0]
                assert str(form_id_b) in keys_used[1]
                assert keys_used[0] != keys_used[1]
        finally:
            _clear_overrides()


class TestUniqueViolationHandling:
    """Bug 1.1 — DB unique violation must return 409, not 500."""

    @pytest.mark.anyio
    async def test_unique_violation_returns_409(self, client):
        """Concurrent duplicate submit → 409 Conflict."""
        form_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=Exception(
                        "duplicate key value violates unique constraint "
                        '"uq_form_responses_form_user" (23505)'
                    ),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "John Doe"}},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                assert "already submitted" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestEmptyOptionsValidation:
    """Bug 1.2 — choice questions must have >= 2 options."""

    def test_dropdown_with_zero_options_rejected(self):
        """QuestionSchema rejects dropdown with no options."""
        from app.schemas.form import QuestionSchema

        with pytest.raises(ValueError, match="requires at least 2 options"):
            QuestionSchema(
                id="q1",
                type="dropdown",
                label="Pick one",
                options=[],
            )

    def test_single_choice_with_one_option_rejected(self):
        """QuestionSchema rejects single_choice with only 1 option."""
        from app.schemas.form import QuestionOption, QuestionSchema

        with pytest.raises(ValueError, match="requires at least 2 options"):
            QuestionSchema(
                id="q1",
                type="single_choice",
                label="Pick one",
                options=[QuestionOption(id="opt1", label="Only option")],
            )

    def test_dropdown_with_two_options_accepted(self):
        """QuestionSchema accepts dropdown with 2 options."""
        from app.schemas.form import QuestionOption, QuestionSchema

        q = QuestionSchema(
            id="q1",
            type="dropdown",
            label="Pick one",
            options=[
                QuestionOption(id="opt1", label="A"),
                QuestionOption(id="opt2", label="B"),
            ],
        )
        assert len(q.options) == 2

    def test_text_question_without_options_accepted(self):
        """QuestionSchema accepts text question without options (not choice type)."""
        from app.schemas.form import QuestionSchema

        q = QuestionSchema(
            id="q1",
            type="text",
            label="Your name",
        )
        assert q.options is None


class TestExportRateLimit:
    """Bug 2.3 — export endpoint must have rate limiting."""

    @pytest.mark.anyio
    async def test_export_rate_limited(self, client):
        """POST /forms/{form_id}/export → 429 when rate limited."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/export",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
                assert "export" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestSchemaLockingSilentDrop:
    """Bug 3.5 — locked form silently drops questions instead of error."""

    @pytest.mark.anyio
    async def test_locked_form_silently_drops_questions(self, mock_pool, mock_conn):
        """update_form on locked form ignores questions, updates title only."""
        from app.services.form import update_form

        form_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": creator_id,
            "title": "Locked Form",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [{"id": "q1", "type": "text", "label": "Name"}],
            "is_schema_locked": True,  # LOCKED
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        updated_row = dict(form_row)
        updated_row["title"] = "New Title"
        creator_row = {"display_name": "Test User"}

        mock_conn.fetchrow = AsyncMock(side_effect=[form_row, updated_row, creator_row])
        mock_conn.fetchval = AsyncMock(return_value=2)

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            # This should NOT raise, even though we pass questions
            result = await update_form(
                form_id=form_id,
                user_id=str(creator_id),
                is_admin=False,
                title="New Title",
                questions=[{"id": "q_new", "type": "text", "label": "New Q"}],
            )

        assert result is not None


class TestDescriptionMaxLength:
    """Bug 3.5 — description must be max 5000 chars."""

    def test_create_form_description_too_long(self):
        """FormCreateRequest rejects description > 5000 chars."""
        from app.schemas.form import FormCreateRequest, QuestionOption, QuestionSchema

        with pytest.raises(Exception):
            FormCreateRequest(
                title="Test",
                description="x" * 5001,
                questions=[
                    QuestionSchema(
                        id="q1",
                        type="dropdown",
                        label="Q",
                        options=[
                            QuestionOption(id="o1", label="A"),
                            QuestionOption(id="o2", label="B"),
                        ],
                    )
                ],
            )

    def test_create_form_description_within_limit(self):
        """FormCreateRequest accepts description <= 5000 chars."""
        from app.schemas.form import FormCreateRequest, QuestionOption, QuestionSchema

        req = FormCreateRequest(
            title="Test",
            description="x" * 5000,
            questions=[
                QuestionSchema(
                    id="q1",
                    type="dropdown",
                    label="Q",
                    options=[
                        QuestionOption(id="o1", label="A"),
                        QuestionOption(id="o2", label="B"),
                    ],
                )
            ],
        )
        assert len(req.description) == 5000


# ──────────────────────────────────────────────────────────────────────
# NEW TESTS: Feature coverage
# ──────────────────────────────────────────────────────────────────────


class TestFormSubmitDeadlineExpired:
    @pytest.mark.anyio
    async def test_submit_form_deadline_expired(self, client):
        """POST /forms/{form_id}/submit → 400 when deadline has passed."""
        from app.core.errors import AppError, ErrorCode

        form_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=AppError(
                        ErrorCode.FORM_001, 400, "This form has passed its deadline."
                    ),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "answer"}},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "deadline" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()


class TestFormSubmitMaxRespondents:
    @pytest.mark.anyio
    async def test_submit_form_max_respondents_reached(self, client):
        """POST /forms/{form_id}/submit → 400 when max respondents reached."""
        form_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=ValueError(
                        "This form has reached its maximum number of responses."
                    ),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "answer"}},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "maximum" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestFormSubmitDuplicate:
    @pytest.mark.anyio
    async def test_submit_form_duplicate_via_value_error(self, client):
        """POST /forms/{form_id}/submit → 409 when ValueError says already submitted."""
        form_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=ValueError("You have already submitted a response to this form."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "answer"}},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                assert "already submitted" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_submit_form_duplicate_via_db_unique_violation(self, client):
        """POST /forms/{form_id}/submit → 409 on DB unique constraint violation."""
        form_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=Exception("duplicate key value violates unique constraint (23505)"),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "answer"}},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                assert "already submitted" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestFormSubmitNonMember:
    @pytest.mark.anyio
    async def test_submit_form_non_member_forbidden(self, client):
        """POST /forms/{form_id}/submit → 403 when non-member submits."""
        form_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.submit_response",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Only SIG members can submit this form."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/submit",
                    json={"answers": {"q1": "answer"}},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "SIG members" in resp.json()["detail"]
        finally:
            _clear_overrides()


class TestFormDeletePermissions:
    @pytest.mark.anyio
    async def test_delete_form_not_found(self, client):
        """DELETE /forms/{form_id} → 404 when form does not exist."""
        form_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.soft_delete_form", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_form_forbidden(self, client):
        """DELETE /forms/{form_id} → 403 when PermissionError raised."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator_id = str(uuid.uuid4())
        form = _make_form(creator_id=creator_id)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.soft_delete_form",
                    new_callable=AsyncMock,
                    side_effect=PermissionError(
                        "Only the form creator or admin can delete this form."
                    ),
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "creator or admin" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestFormUpdateLocked:
    @pytest.mark.anyio
    async def test_update_locked_form_drops_questions(self, client):
        """PUT /forms/{form_id} → 200 even when questions provided on locked form."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form = _make_form(creator_id=user_id)
        form["id"] = str(form_id)
        form["is_schema_locked"] = True

        updated_form = dict(form)
        updated_form["title"] = "New Title"

        try:
            _override_auth("ADMIN", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.update_form", new_callable=AsyncMock, return_value=updated_form),
            ):
                resp = await client.put(
                    f"/api/v1/forms/{form_id}",
                    json={
                        "title": "New Title",
                        "questions": [
                            {"id": "q1", "type": "text", "label": "Name", "required": True}
                        ],
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["title"] == "New Title"
        finally:
            _clear_overrides()


class TestFormListEmpty:
    @pytest.mark.anyio
    async def test_list_forms_empty(self, client):
        """GET /sigs/{sig_id}/forms → 200 with empty list."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.list_forms_by_sig",
                    new_callable=AsyncMock,
                    return_value=([], 0),
                ),
            ):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/forms",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["forms"] == []
                assert data["total"] == 0
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_forms_with_pagination(self, client):
        """GET /sigs/{sig_id}/forms?page=2&page_size=5 → pagination params forwarded."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.list_forms_by_sig",
                    new_callable=AsyncMock,
                    return_value=([], 0),
                ) as mock_list,
            ):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/forms?page=2&page_size=5",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_list.assert_called_once_with(sig_id, page=2, page_size=5)
        finally:
            _clear_overrides()


class TestFormResponsesList:
    @pytest.mark.anyio
    async def test_list_responses_success(self, client):
        """GET /forms/{form_id}/responses → 200 for SIG admin."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)

        response_item = {
            "id": str(uuid.uuid4()),
            "form_id": str(form_id),
            "user_id": str(uuid.uuid4()),
            "display_name": "Test User",
            "username": "testuser",
            "answers": {"q1": "Answer"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.list_form_responses",
                    new_callable=AsyncMock,
                    return_value=([response_item], 1),
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/responses",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["responses"]) == 1
                assert data["responses"][0]["display_name"] == "Test User"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_responses_forbidden_non_admin(self, client):
        """GET /forms/{form_id}/responses → 403 for non-admin."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/responses",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "admin" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestFormExportPermissions:
    @pytest.mark.anyio
    async def test_export_form_rate_limited(self, client):
        """POST /forms/{form_id}/export → 429 when rate limited."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/export",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
                assert "export" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestFormSchemaValidation:
    """Pydantic schema validation tests for form creation and questions."""

    def test_form_create_empty_title_rejected(self):
        """FormCreateRequest rejects empty title."""
        from app.schemas.form import FormCreateRequest, QuestionOption, QuestionSchema

        with pytest.raises(Exception):
            FormCreateRequest(
                title="",
                questions=[
                    QuestionSchema(
                        id="q1",
                        type="dropdown",
                        label="Q",
                        options=[
                            QuestionOption(id="o1", label="A"),
                            QuestionOption(id="o2", label="B"),
                        ],
                    )
                ],
            )

    def test_form_create_no_questions_rejected(self):
        """FormCreateRequest rejects empty questions list."""
        from app.schemas.form import FormCreateRequest

        with pytest.raises(Exception):
            FormCreateRequest(
                title="Valid Title",
                questions=[],
            )

    def test_form_question_choice_needs_min_2_options(self):
        """QuestionSchema rejects choice question with fewer than 2 options."""
        from app.schemas.form import QuestionOption, QuestionSchema

        with pytest.raises(ValueError, match="requires at least 2 options"):
            QuestionSchema(
                id="q1",
                type="single_choice",
                label="Pick one",
                options=[QuestionOption(id="o1", label="Only one")],
            )

    def test_form_question_rating_min_greater_than_max_rejected(self):
        """Rating answer with value outside inverted min/max range is rejected."""
        from app.services.form import _validate_answers

        questions = [{"id": "q1", "type": "rating", "label": "Rate", "min": 5, "max": 1}]
        # Any integer should fail validation since min > max makes range impossible
        with pytest.raises(ValueError, match="must be between"):
            _validate_answers(questions, {"q1": 3})


# ──────────────────────────────────────────────────────────────────────
# NEW TESTS: sanitize_html applied on form create/update
# ──────────────────────────────────────────────────────────────────────


class TestFormDescriptionSanitization:
    """Verify sanitize_html is called when creating or updating a form with a description."""

    @pytest.mark.anyio
    async def test_create_form_sanitizes_description(self, client) -> None:
        """POST /sigs/{sig_id}/forms — description containing script tags is sanitized."""
        sig_id = uuid.uuid4()
        form = _make_form(sig_id=str(sig_id))
        form["description"] = "<p>clean</p>"  # what the service returns after sanitizing

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_form", new_callable=AsyncMock, return_value=form
                ) as mock_create,
                patch(
                    f"{_EP}.sanitize_html",
                    return_value="<p>clean</p>",
                ) as mock_sanitize,
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/forms",
                    json={
                        "title": "Test Form",
                        "description": "<script>alert(1)</script><p>clean</p>",
                        "questions": [
                            {"id": "q1", "type": "text", "label": "Name", "required": True}
                        ],
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                # sanitize_html must have been called with the raw description
                mock_sanitize.assert_called_once()
                call_arg = mock_sanitize.call_args[0][0]
                assert "<script>" in call_arg
                # create_form must receive the sanitized description
                _, kwargs = mock_create.call_args
                assert kwargs.get("description") == "<p>clean</p>"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_form_null_description_skips_sanitize(self, client) -> None:
        """POST /sigs/{sig_id}/forms — None description does not call sanitize_html."""
        sig_id = uuid.uuid4()
        form = _make_form(sig_id=str(sig_id))
        form["description"] = None

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_form", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}.sanitize_html", return_value="") as mock_sanitize,
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/forms",
                    json={
                        "title": "Test Form",
                        "questions": [
                            {"id": "q1", "type": "text", "label": "Name", "required": True}
                        ],
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                mock_sanitize.assert_not_called()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_form_sanitizes_description(self, client) -> None:
        """PUT /forms/{form_id} — description with XSS payload gets sanitized."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form = _make_form(creator_id=user_id)
        form["id"] = str(form_id)
        form["description"] = "<p>safe</p>"

        updated_form = dict(form)
        updated_form["description"] = "<p>safe</p>"

        try:
            _override_auth("ADMIN", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.update_form", new_callable=AsyncMock, return_value=updated_form
                ) as mock_update,
                patch(
                    f"{_EP}.sanitize_html",
                    return_value="<p>safe</p>",
                ) as mock_sanitize,
            ):
                resp = await client.put(
                    f"/api/v1/forms/{form_id}",
                    json={
                        "title": "Title",
                        "description": '<img src=x onerror="alert(1)"><p>safe</p>',
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_sanitize.assert_called_once()
                _, kwargs = mock_update.call_args
                assert kwargs.get("description") == "<p>safe</p>"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_form_null_description_skips_sanitize(self, client) -> None:
        """PUT /forms/{form_id} — omitting description does not call sanitize_html."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form = _make_form(creator_id=user_id)
        form["id"] = str(form_id)

        try:
            _override_auth("ADMIN", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.update_form", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}.sanitize_html", return_value="") as mock_sanitize,
            ):
                resp = await client.put(
                    f"/api/v1/forms/{form_id}",
                    json={"title": "New Title"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_sanitize.assert_not_called()
        finally:
            _clear_overrides()


class TestGetFormAccessControl:
    """GET /forms/{form_id} respects allow_non_members flag."""

    @pytest.mark.anyio
    async def test_non_member_blocked_when_allow_non_members_false(self, client):
        """Non-SIG-member gets 403 when form has allow_non_members=False."""
        form_id = uuid.uuid4()
        form = _make_form(allow_non_members=False)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "SIG members" in resp.json()["detail"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sig_member_allowed_when_allow_non_members_false(self, client):
        """SIG member can view form even when allow_non_members=False."""
        form_id = uuid.uuid4()
        form = _make_form(allow_non_members=False)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_always_allowed(self, client):
        """Platform admin can view form regardless of allow_non_members."""
        form_id = uuid.uuid4()
        form = _make_form(allow_non_members=False)
        form["id"] = str(form_id)

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_anyone_allowed_when_allow_non_members_true(self, client):
        """Any logged-in user can view form when allow_non_members=True."""
        form_id = uuid.uuid4()
        form = _make_form(allow_non_members=True)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


# ──────────────────────────────────────────────────────────────────────
# NEW TESTS: my-response, stats, has_responded, response_count
# ──────────────────────────────────────────────────────────────────────


class TestGetMyResponse:
    """GET /forms/{form_id}/my-response tests."""

    @pytest.mark.anyio
    async def test_my_response_success(self, client) -> None:
        """GET /forms/{form_id}/my-response → 200 when user has responded."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form = _make_form()
        form["id"] = str(form_id)
        now = datetime.now(timezone.utc).isoformat()
        user_response = {
            "id": str(uuid.uuid4()),
            "form_id": str(form_id),
            "user_id": user_id,
            "answers": {"q1": "My answer"},
            "created_at": now,
        }

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
                patch(
                    f"{_EP}.get_user_response",
                    new_callable=AsyncMock,
                    return_value=user_response,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/my-response",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["form_id"] == str(form_id)
                assert data["user_id"] == user_id
                assert data["answers"] == {"q1": "My answer"}
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_my_response_not_found(self, client) -> None:
        """GET /forms/{form_id}/my-response → 404 when user has not responded."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
                patch(
                    f"{_EP}.get_user_response",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/my-response",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "no response" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_my_response_form_not_found(self, client) -> None:
        """GET /forms/{form_id}/my-response → 404 when form does not exist."""
        form_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=None):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/my-response",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "form not found" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_my_response_returns_correct_schema(self, client) -> None:
        """GET /forms/{form_id}/my-response returns all required fields."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        response_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        form = _make_form()
        form["id"] = str(form_id)
        user_response = {
            "id": response_id,
            "form_id": str(form_id),
            "user_id": user_id,
            "answers": {"q1": "Answer", "q2": ["opt1", "opt2"]},
            "created_at": now,
        }

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
                patch(
                    f"{_EP}.get_user_response",
                    new_callable=AsyncMock,
                    return_value=user_response,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/my-response",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == response_id
                assert data["form_id"] == str(form_id)
                assert data["user_id"] == user_id
                assert data["answers"]["q2"] == ["opt1", "opt2"]
                assert data["created_at"] == now
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_my_response_non_member_gets_403(self, client) -> None:
        """GET /forms/{form_id}/my-response → 403 when allow_non_members=False
        and user is not a SIG member."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        # Form restricts to SIG members only
        form = _make_form(allow_non_members=False)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/my-response",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "sig members" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()


class TestGetFormStats:
    """GET /forms/{form_id}/stats tests."""

    @pytest.mark.anyio
    async def test_stats_success_as_admin(self, client) -> None:
        """GET /forms/{form_id}/stats → 200 for SIG admin."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)
        stats = {
            "form_id": str(form_id),
            "total_responses": 5,
            "question_stats": [
                {
                    "question_id": "q1",
                    "question_type": "text",
                    "question_label": "Name",
                    "stats": {"count": 5},
                }
            ],
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_stats", new_callable=AsyncMock, return_value=stats),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/stats",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["form_id"] == str(form_id)
                assert data["total_responses"] == 5
                assert len(data["question_stats"]) == 1
                assert data["question_stats"][0]["question_id"] == "q1"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_stats_success_as_creator(self, client) -> None:
        """GET /forms/{form_id}/stats → 200 for form creator (non-admin)."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form = _make_form(creator_id=user_id)
        form["id"] = str(form_id)
        stats = {
            "form_id": str(form_id),
            "total_responses": 3,
            "question_stats": [],
        }

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(f"{_EP}.get_form_stats", new_callable=AsyncMock, return_value=stats),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/stats",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total_responses"] == 3
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_stats_forbidden_non_admin_non_creator(self, client) -> None:
        """GET /forms/{form_id}/stats → 403 for non-admin, non-creator."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator_id = str(uuid.uuid4())
        form = _make_form(creator_id=creator_id)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/stats",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "creator or admin" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_stats_form_not_found(self, client) -> None:
        """GET /forms/{form_id}/stats → 404 when form does not exist."""
        form_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=None),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/stats",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "form not found" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_stats_with_choice_questions(self, client) -> None:
        """GET /forms/{form_id}/stats returns option counts and percentages."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)
        stats = {
            "form_id": str(form_id),
            "total_responses": 10,
            "question_stats": [
                {
                    "question_id": "q1",
                    "question_type": "single_choice",
                    "question_label": "Favorite color",
                    "stats": {
                        "options": [
                            {
                                "option_id": "opt1",
                                "option_label": "Red",
                                "count": 6,
                                "percentage": 60.0,
                            },
                            {
                                "option_id": "opt2",
                                "option_label": "Blue",
                                "count": 4,
                                "percentage": 40.0,
                            },
                        ]
                    },
                }
            ],
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_stats", new_callable=AsyncMock, return_value=stats),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/stats",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                opts = data["question_stats"][0]["stats"]["options"]
                assert len(opts) == 2
                assert opts[0]["count"] == 6
                assert opts[0]["percentage"] == 60.0
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_stats_with_rating_question(self, client) -> None:
        """GET /forms/{form_id}/stats returns rating avg/min/max/distribution."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)
        stats = {
            "form_id": str(form_id),
            "total_responses": 3,
            "question_stats": [
                {
                    "question_id": "q1",
                    "question_type": "rating",
                    "question_label": "Rate us",
                    "stats": {
                        "average": 3.67,
                        "min": 2,
                        "max": 5,
                        "count": 3,
                        "distribution": {"2": 1, "4": 1, "5": 1},
                    },
                }
            ],
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_stats", new_callable=AsyncMock, return_value=stats),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/stats",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                rating_stats = data["question_stats"][0]["stats"]
                assert rating_stats["average"] == 3.67
                assert rating_stats["min"] == 2
                assert rating_stats["max"] == 5
                assert rating_stats["count"] == 3
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_stats_forbidden_for_regular_user(self, client) -> None:
        """GET /forms/{form_id}/stats → 403 for a MEMBER who is neither creator nor SIG admin."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator_id = str(uuid.uuid4())
        form = _make_form(creator_id=creator_id)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}/stats",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
                assert "creator or admin" in resp.json()["detail"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_stats_requires_authentication(self, client) -> None:
        """GET /forms/{form_id}/stats → 401 for unauthenticated request."""
        form_id = uuid.uuid4()
        # No _override_auth — no valid session cookie or token
        resp = await client.get(f"/api/v1/forms/{form_id}/stats")
        assert resp.status_code in (401, 403)


class TestFormStatsService:
    """Unit tests for the get_form_stats service function."""

    @pytest.mark.anyio
    async def test_stats_single_choice(self) -> None:
        """get_form_stats correctly counts single_choice answers."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Pick one",
                    "options": [
                        {"id": "opt1", "label": "A"},
                        {"id": "opt2", "label": "B"},
                    ],
                }
            ],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }
        responses = [
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": "opt1"},
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": "opt1"},
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": "opt2"},
                "created_at": now,
            },
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 3),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
        ):
            result = await get_form_stats(form_id)

        assert result["total_responses"] == 3
        opts = result["question_stats"][0]["stats"]["options"]
        opt1 = next(o for o in opts if o["option_id"] == "opt1")
        opt2 = next(o for o in opts if o["option_id"] == "opt2")
        assert opt1["count"] == 2
        assert opt1["percentage"] == 66.7
        assert opt2["count"] == 1
        assert opt2["percentage"] == 33.3

    @pytest.mark.anyio
    async def test_stats_multiple_choice(self) -> None:
        """get_form_stats correctly counts multiple_choice answers."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [
                {
                    "id": "q1",
                    "type": "multiple_choice",
                    "label": "Select all",
                    "options": [
                        {"id": "opt1", "label": "A"},
                        {"id": "opt2", "label": "B"},
                        {"id": "opt3", "label": "C"},
                    ],
                }
            ],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }
        responses = [
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": ["opt1", "opt2"]},
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": ["opt2", "opt3"]},
                "created_at": now,
            },
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 2),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
        ):
            result = await get_form_stats(form_id)

        opts = result["question_stats"][0]["stats"]["options"]
        opt1 = next(o for o in opts if o["option_id"] == "opt1")
        opt2 = next(o for o in opts if o["option_id"] == "opt2")
        opt3 = next(o for o in opts if o["option_id"] == "opt3")
        assert opt1["count"] == 1
        assert opt2["count"] == 2
        assert opt3["count"] == 1

    @pytest.mark.anyio
    async def test_stats_rating(self) -> None:
        """get_form_stats correctly computes rating avg/min/max/distribution."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [{"id": "q1", "type": "rating", "label": "Rate", "min": 1, "max": 5}],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }
        responses = [
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": 3},
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": 5},
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": 4},
                "created_at": now,
            },
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 3),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
        ):
            result = await get_form_stats(form_id)

        stats = result["question_stats"][0]["stats"]
        assert stats["average"] == 4.0
        assert stats["min"] == 3
        assert stats["max"] == 5
        assert stats["count"] == 3
        assert stats["distribution"] == {3: 1, 4: 1, 5: 1}

    @pytest.mark.anyio
    async def test_stats_text_count(self) -> None:
        """get_form_stats correctly counts text/textarea responses."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [{"id": "q1", "type": "text", "label": "Name"}],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }
        responses = [
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": "Alice"},
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": ""},
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": "Bob"},
                "created_at": now,
            },
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 3),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
        ):
            result = await get_form_stats(form_id)

        assert result["question_stats"][0]["stats"]["count"] == 2

    @pytest.mark.anyio
    async def test_stats_file_upload_count(self) -> None:
        """get_form_stats correctly counts file_upload responses."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [{"id": "q1", "type": "file_upload", "label": "Upload"}],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }
        responses = [
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": {"key": "files/abc.pdf", "filename": "abc.pdf"}},
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": None},
                "created_at": now,
            },
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 2),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
        ):
            result = await get_form_stats(form_id)

        assert result["question_stats"][0]["stats"]["count"] == 1

    @pytest.mark.anyio
    async def test_stats_empty_responses(self) -> None:
        """get_form_stats returns zeros when no responses exist."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Pick",
                    "options": [
                        {"id": "opt1", "label": "A"},
                        {"id": "opt2", "label": "B"},
                    ],
                },
                {"id": "q2", "type": "rating", "label": "Rate", "min": 1, "max": 5},
            ],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 0),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await get_form_stats(form_id)

        assert result["total_responses"] == 0
        choice_stats = result["question_stats"][0]["stats"]
        assert all(o["count"] == 0 for o in choice_stats["options"])
        assert all(o["percentage"] == 0.0 for o in choice_stats["options"])
        rating_stats = result["question_stats"][1]["stats"]
        assert rating_stats["average"] == 0.0
        assert rating_stats["count"] == 0

    @pytest.mark.anyio
    async def test_stats_form_not_found_raises(self) -> None:
        """get_form_stats raises ValueError when form does not exist."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()

        with patch(
            "app.services.form.form_repo.find_by_id", new_callable=AsyncMock, return_value=(None, 0)
        ):
            with pytest.raises(ValueError, match="Form not found"):
                await get_form_stats(form_id)


class TestFormHasResponded:
    """GET /forms/{form_id} includes has_responded field."""

    @pytest.mark.anyio
    async def test_get_form_includes_has_responded_true(self, client) -> None:
        """GET /forms/{form_id} → has_responded=true when user has responded."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)
        form["has_responded"] = True

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["has_responded"] is True
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_form_includes_has_responded_false(self, client) -> None:
        """GET /forms/{form_id} → has_responded=false when user has not responded."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)
        form["has_responded"] = False

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["has_responded"] is False
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_form_passes_user_id(self, client) -> None:
        """GET /forms/{form_id} passes current user_id to get_form_by_id."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form = _make_form()
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(
                    f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form
                ) as mock_get,
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_get.assert_called_once_with(form_id, user_id=user_id)
        finally:
            _clear_overrides()


class TestFormResponseCount:
    """Verify response_count is already included in form detail response."""

    @pytest.mark.anyio
    async def test_get_form_includes_response_count(self, client) -> None:
        """GET /forms/{form_id} → response body includes response_count field."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)
        form["response_count"] = 42

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.sig_repo.get_member_role",
                    new_callable=AsyncMock,
                    return_value="MEMBER",
                ),
            ):
                resp = await client.get(
                    f"/api/v1/forms/{form_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["response_count"] == 42
        finally:
            _clear_overrides()


class TestGetUserResponseService:
    """Unit tests for the get_user_response service function."""

    @pytest.mark.anyio
    async def test_get_user_response_found(self) -> None:
        """get_user_response returns formatted dict when response exists."""
        from app.services.form import get_user_response

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        response_row = {
            "id": uuid.uuid4(),
            "form_id": form_id,
            "user_id": uuid.UUID(user_id),
            "answers": {"q1": "Answer"},
            "created_at": now,
        }

        with patch(
            "app.services.form.form_repo.find_user_response",
            new_callable=AsyncMock,
            return_value=response_row,
        ):
            result = await get_user_response(form_id, user_id)

        assert result is not None
        assert result["form_id"] == str(form_id)
        assert result["user_id"] == user_id
        assert result["answers"] == {"q1": "Answer"}
        assert result["created_at"] == now.isoformat()

    @pytest.mark.anyio
    async def test_get_user_response_not_found(self) -> None:
        """get_user_response returns None when no response exists."""
        from app.services.form import get_user_response

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with patch(
            "app.services.form.form_repo.find_user_response",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await get_user_response(form_id, user_id)

        assert result is None

    @pytest.mark.anyio
    async def test_get_user_response_parses_json_string(self) -> None:
        """get_user_response handles answers stored as JSON string."""
        from app.services.form import get_user_response

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        response_row = {
            "id": uuid.uuid4(),
            "form_id": form_id,
            "user_id": uuid.UUID(user_id),
            "answers": '{"q1": "Answer"}',
            "created_at": now,
        }

        with patch(
            "app.services.form.form_repo.find_user_response",
            new_callable=AsyncMock,
            return_value=response_row,
        ):
            result = await get_user_response(form_id, user_id)

        assert result is not None
        assert result["answers"] == {"q1": "Answer"}


class TestGetFormByIdService:
    """Unit tests for get_form_by_id with user_id parameter."""

    @pytest.mark.anyio
    async def test_get_form_by_id_with_user_id(self) -> None:
        """get_form_by_id includes has_responded when user_id is provided."""
        from app.services.form import get_form_by_id

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 5),
            ),
            patch(
                "app.services.form.form_repo.has_user_responded",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await get_form_by_id(form_id, user_id=user_id)

        assert result is not None
        assert result["has_responded"] is True
        assert result["response_count"] == 5

    @pytest.mark.anyio
    async def test_get_form_by_id_without_user_id(self) -> None:
        """get_form_by_id omits has_responded when user_id is None."""
        from app.services.form import get_form_by_id

        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }

        with patch(
            "app.services.form.form_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=(form_row, 0),
        ):
            result = await get_form_by_id(form_id)

        assert result is not None
        assert "has_responded" not in result

    @pytest.mark.anyio
    async def test_get_form_by_id_not_found(self) -> None:
        """get_form_by_id returns None when form does not exist."""
        from app.services.form import get_form_by_id

        form_id = uuid.uuid4()

        with patch(
            "app.services.form.form_repo.find_by_id", new_callable=AsyncMock, return_value=(None, 0)
        ):
            result = await get_form_by_id(form_id, user_id=str(uuid.uuid4()))

        assert result is None


class TestFormStatsDropdownType:
    """Verify dropdown question type is treated like single_choice in stats."""

    @pytest.mark.anyio
    async def test_stats_dropdown(self) -> None:
        """get_form_stats correctly counts dropdown answers."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": [
                {
                    "id": "q1",
                    "type": "dropdown",
                    "label": "Select",
                    "options": [
                        {"id": "opt1", "label": "X"},
                        {"id": "opt2", "label": "Y"},
                    ],
                }
            ],
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Test User",
        }
        responses = [
            {
                "id": uuid.uuid4(),
                "form_id": form_id,
                "user_id": uuid.uuid4(),
                "answers": {"q1": "opt1"},
                "created_at": now,
            },
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 1),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
        ):
            result = await get_form_stats(form_id)

        opts = result["question_stats"][0]["stats"]["options"]
        opt1 = next(o for o in opts if o["option_id"] == "opt1")
        assert opt1["count"] == 1
        assert opt1["percentage"] == 100.0


# ──────────────────────────────────────────────────────────────────────
# NEW TESTS: File size validation, permission check, export TTL
# ──────────────────────────────────────────────────────────────────────


class TestFileSizeValidation:
    """Server-side file size validation for file_upload questions."""

    @pytest.mark.anyio
    async def test_oversized_file_rejected(self):
        """_validate_file_sizes raises ValueError when file exceeds max_size_mb."""
        from app.services.form import _validate_file_sizes

        questions = [
            {
                "id": "q1",
                "type": "file_upload",
                "label": "Upload",
                "max_size_mb": 5,
            }
        ]
        answers = {"q1": {"key": "forms/uploads/test.pdf", "filename": "test.pdf"}}

        # 6 MB = 6 * 1024 * 1024 bytes — exceeds 5 MB limit
        with patch(
            "app.core.async_storage.get_file_size",
            new_callable=AsyncMock,
            return_value=6 * 1024 * 1024,
        ):
            with pytest.raises(ValueError, match="exceeds the maximum size of 5 MB"):
                await _validate_file_sizes(questions, answers)

    @pytest.mark.anyio
    async def test_file_within_limit_accepted(self):
        """_validate_file_sizes passes when file is within max_size_mb."""
        from app.services.form import _validate_file_sizes

        questions = [
            {
                "id": "q1",
                "type": "file_upload",
                "label": "Upload",
                "max_size_mb": 10,
            }
        ]
        answers = {"q1": {"key": "forms/uploads/small.pdf", "filename": "small.pdf"}}

        # 5 MB — within 10 MB limit
        with patch(
            "app.core.async_storage.get_file_size",
            new_callable=AsyncMock,
            return_value=5 * 1024 * 1024,
        ):
            # Should not raise
            await _validate_file_sizes(questions, answers)

    @pytest.mark.anyio
    async def test_file_exactly_at_limit_accepted(self):
        """_validate_file_sizes passes when file is exactly at max_size_mb."""
        from app.services.form import _validate_file_sizes

        questions = [
            {
                "id": "q1",
                "type": "file_upload",
                "label": "Upload",
                "max_size_mb": 5,
            }
        ]
        answers = {"q1": {"key": "forms/uploads/exact.pdf", "filename": "exact.pdf"}}

        # Exactly 5 MB
        with patch(
            "app.core.async_storage.get_file_size",
            new_callable=AsyncMock,
            return_value=5 * 1024 * 1024,
        ):
            # Should not raise — equal to limit, not exceeding
            await _validate_file_sizes(questions, answers)

    @pytest.mark.anyio
    async def test_no_max_size_skips_check(self):
        """_validate_file_sizes skips check when max_size_mb is not set."""
        from app.services.form import _validate_file_sizes

        questions = [
            {
                "id": "q1",
                "type": "file_upload",
                "label": "Upload",
                # no max_size_mb
            }
        ]
        answers = {"q1": {"key": "forms/uploads/big.pdf", "filename": "big.pdf"}}

        with patch(
            "app.core.async_storage.get_file_size",
            new_callable=AsyncMock,
            return_value=999 * 1024 * 1024,
        ) as mock_size:
            await _validate_file_sizes(questions, answers)
            # get_file_size should not be called when no limit
            mock_size.assert_not_called()

    @pytest.mark.anyio
    async def test_non_file_questions_skipped(self):
        """_validate_file_sizes ignores non-file_upload questions."""
        from app.services.form import _validate_file_sizes

        questions = [
            {"id": "q1", "type": "text", "label": "Name"},
            {"id": "q2", "type": "rating", "label": "Rate"},
        ]
        answers = {"q1": "John", "q2": 5}

        with patch(
            "app.core.async_storage.get_file_size",
            new_callable=AsyncMock,
        ) as mock_size:
            await _validate_file_sizes(questions, answers)
            mock_size.assert_not_called()

    @pytest.mark.anyio
    async def test_empty_file_answer_skipped(self):
        """_validate_file_sizes skips file questions with no answer."""
        from app.services.form import _validate_file_sizes

        questions = [
            {
                "id": "q1",
                "type": "file_upload",
                "label": "Upload",
                "max_size_mb": 5,
            }
        ]
        answers = {}  # no answer for q1

        with patch(
            "app.core.async_storage.get_file_size",
            new_callable=AsyncMock,
        ) as mock_size:
            await _validate_file_sizes(questions, answers)
            mock_size.assert_not_called()

    @pytest.mark.anyio
    async def test_file_size_validation_in_submit_response(self):
        """submit_response calls _validate_file_sizes during submission."""
        import json

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        questions = [
            {
                "id": "q1",
                "type": "file_upload",
                "label": "Upload",
                "required": True,
                "max_size_mb": 2,
            }
        ]
        form_row = {
            "id": form_id,
            "sig_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "title": "Test Form",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": json.dumps(questions),
            "is_schema_locked": False,
            "is_deleted": False,
            "allow_non_members": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        mock_conn = AsyncMock()
        mock_conn.transaction = MagicMock()
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction.return_value = tx

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        answers = {"q1": {"key": "forms/uploads/large.pdf", "filename": "large.pdf"}}

        with (
            patch(f"{_SVC}.get_pool", return_value=mock_pool),
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
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                return_value=3 * 1024 * 1024,  # 3 MB > 2 MB limit
            ),
        ):
            from app.services.form import submit_response

            with pytest.raises(ValueError, match="exceeds the maximum size"):
                await submit_response(form_id, user_id, answers)


class TestUpdateFormPermissionConsolidated:
    """Verify the consolidated permission check in update_existing_form."""

    @pytest.mark.anyio
    async def test_sig_admin_can_update_others_form(self, client):
        """PUT /forms/{form_id} → 200 when SIG admin updates another user's form."""
        form_id = uuid.uuid4()
        admin_user_id = str(uuid.uuid4())
        creator_id = str(uuid.uuid4())
        form = _make_form(creator_id=creator_id)
        form["id"] = str(form_id)
        updated_form = dict(form)
        updated_form["title"] = "Admin Updated"

        try:
            _override_auth("MEMBER", user_id=admin_user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.update_form", new_callable=AsyncMock, return_value=updated_form
                ) as mock_update,
            ):
                resp = await client.put(
                    f"/api/v1/forms/{form_id}",
                    json={"title": "Admin Updated"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                # is_admin passed to update_form should be True (from _is_sig_admin)
                _, kwargs = mock_update.call_args
                assert kwargs["is_admin"] is True
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_platform_admin_is_admin_via_is_sig_admin(self, client):
        """PUT /forms/{form_id} → _is_sig_admin returns True for SUPER_ADMIN."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        form = _make_form(creator_id=str(uuid.uuid4()))
        form["id"] = str(form_id)
        updated_form = dict(form)
        updated_form["title"] = "Super Admin Updated"

        try:
            _override_auth("SUPER_ADMIN", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                # _is_sig_admin checks platform admin roles internally
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.update_form", new_callable=AsyncMock, return_value=updated_form
                ) as mock_update,
            ):
                resp = await client.put(
                    f"/api/v1/forms/{form_id}",
                    json={"title": "Super Admin Updated"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                _, kwargs = mock_update.call_args
                assert kwargs["is_admin"] is True
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_admin_non_creator_cannot_update(self, client):
        """PUT /forms/{form_id} → 403 when regular member is not creator or admin."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator_id = str(uuid.uuid4())
        form = _make_form(creator_id=creator_id)
        form["id"] = str(form_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.put(
                    f"/api/v1/forms/{form_id}",
                    json={"title": "Attempt"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_creator_can_update_own_form(self, client):
        """PUT /forms/{form_id} → 200 when creator updates own form (not admin)."""
        form_id = uuid.uuid4()
        creator_id = str(uuid.uuid4())
        form = _make_form(creator_id=creator_id)
        form["id"] = str(form_id)
        updated_form = dict(form)
        updated_form["title"] = "Creator Updated"

        try:
            _override_auth("MEMBER", user_id=creator_id)
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=False),
                patch(
                    f"{_EP}.update_form", new_callable=AsyncMock, return_value=updated_form
                ) as mock_update,
            ):
                resp = await client.put(
                    f"/api/v1/forms/{form_id}",
                    json={"title": "Creator Updated"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                _, kwargs = mock_update.call_args
                # is_admin should be False since _is_sig_admin returns False
                assert kwargs["is_admin"] is False
        finally:
            _clear_overrides()


class TestExportTaskOwnershipTTL:
    """Verify export task ownership Redis key uses 24-hour TTL."""

    @pytest.mark.anyio
    async def test_export_sets_24h_ttl(self, client):
        """POST /forms/{form_id}/export → sets task_owner key with ex=86400."""
        form_id = uuid.uuid4()
        form = _make_form()
        form["id"] = str(form_id)

        mock_task = MagicMock()
        mock_task.id = "celery-task-456"

        mock_export_module = MagicMock()
        mock_export_module.export_form_csv.delay.return_value = mock_task

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        try:
            _, uid = _override_auth("ADMIN")
            with (
                patch(f"{_EP}.get_form_by_id", new_callable=AsyncMock, return_value=form),
                patch(f"{_EP}._is_sig_admin", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch.dict("sys.modules", {"app.tasks.form_export": mock_export_module}),
                patch("app.core.redis.get_redis", return_value=mock_redis),
            ):
                resp = await client.post(
                    f"/api/v1/forms/{form_id}/export",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 202
                assert resp.json()["task_id"] == "celery-task-456"
                # Verify 24-hour TTL (86400 seconds)
                mock_redis.set.assert_awaited_once_with(
                    "task_owner:celery-task-456", uid, ex=86400
                )
        finally:
            _clear_overrides()


class TestIsSigAdminHelper:
    """Verify _is_sig_admin helper covers all cases correctly."""

    @pytest.mark.anyio
    async def test_super_admin_returns_true(self):
        """SUPER_ADMIN role should always return True without querying SIG membership."""
        from app.api.v1.endpoints.forms import _is_sig_admin

        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with patch(
            f"{_EP}.sig_repo.get_member_role", new_callable=AsyncMock
        ) as mock_role:
            result = await _is_sig_admin(sig_id, user_id, "SUPER_ADMIN")
            assert result is True
            # Should NOT query SIG membership for platform admins
            mock_role.assert_not_called()

    @pytest.mark.anyio
    async def test_platform_admin_returns_true(self):
        """ADMIN role should always return True without querying SIG membership."""
        from app.api.v1.endpoints.forms import _is_sig_admin

        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with patch(
            f"{_EP}.sig_repo.get_member_role", new_callable=AsyncMock
        ) as mock_role:
            result = await _is_sig_admin(sig_id, user_id, "ADMIN")
            assert result is True
            mock_role.assert_not_called()

    @pytest.mark.anyio
    async def test_sig_admin_returns_true(self):
        """SIG ADMIN member role should return True."""
        from app.api.v1.endpoints.forms import _is_sig_admin

        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with patch(
            f"{_EP}.sig_repo.get_member_role",
            new_callable=AsyncMock,
            return_value="ADMIN",
        ):
            result = await _is_sig_admin(sig_id, user_id, "MEMBER")
            assert result is True

    @pytest.mark.anyio
    async def test_sig_sub_admin_returns_true(self):
        """SIG SUB_ADMIN member role should return True."""
        from app.api.v1.endpoints.forms import _is_sig_admin

        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with patch(
            f"{_EP}.sig_repo.get_member_role",
            new_callable=AsyncMock,
            return_value="SUB_ADMIN",
        ):
            result = await _is_sig_admin(sig_id, user_id, "MEMBER")
            assert result is True

    @pytest.mark.anyio
    async def test_regular_member_returns_false(self):
        """Regular SIG member should return False."""
        from app.api.v1.endpoints.forms import _is_sig_admin

        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with patch(
            f"{_EP}.sig_repo.get_member_role",
            new_callable=AsyncMock,
            return_value="MEMBER",
        ):
            result = await _is_sig_admin(sig_id, user_id, "MEMBER")
            assert result is False

    @pytest.mark.anyio
    async def test_non_member_returns_false(self):
        """Non-member (no SIG role) should return False."""
        from app.api.v1.endpoints.forms import _is_sig_admin

        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with patch(
            f"{_EP}.sig_repo.get_member_role",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _is_sig_admin(sig_id, user_id, "MEMBER")
            assert result is False
