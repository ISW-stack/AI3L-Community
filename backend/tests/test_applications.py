"""Tests for applications endpoints.

apply success, non-guest rejected, list admin, review approve,
my-application status, password policy, username uniqueness.
Also covers atomic check+insert transaction safety in application_repo.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.applications"
_EP_USERS = "app.api.v1.endpoints.users"
_REPO = "app.repositories.application_repo"
_SVC = "app.services.application"

_VALID_APPLY_BODY = {
    "username": "newuser",
    "password": "Passw0rd!",
    "display_name": "New User",
    "description": "I'd like to join the community.",
}


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


def _make_application(user_id=None):
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID(user_id) if user_id else uuid.uuid4(),
        "username": "guest1",
        "display_name": "Guest User",
        "description": "I'd like to join",
        "status": "PENDING",
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": now,
    }


# ── Apply endpoint ──────────────────────────────────────────


class TestApplyMembership:
    @pytest.mark.anyio
    async def test_apply_success(self, client):
        """POST /users/apply-member → 200 for GUEST with valid body."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_application", new_callable=AsyncMock),
            ):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=_VALID_APPLY_BODY,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "submitted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_guest_rejected(self, client):
        """POST /users/apply-member → 422 for non-GUEST."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=_VALID_APPLY_BODY,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_apply_weak_password_rejected(self, client):
        """POST /users/apply-member → 400 when password fails policy."""
        user_id = str(uuid.uuid4())
        body = {**_VALID_APPLY_BODY, "password": "weak"}

        try:
            _override_auth("GUEST", user_id=user_id)
            resp = await client.post(
                "/api/v1/users/apply-member",
                json=body,
                headers={"Authorization": "Bearer fake"},
            )
            # Pydantic validation (min 8 chars) rejects first → 422
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_apply_password_no_special_char(self, client):
        """POST /users/apply-member → 400 when password lacks special char."""
        user_id = str(uuid.uuid4())
        body = {**_VALID_APPLY_BODY, "password": "Passw0rdx"}

        try:
            _override_auth("GUEST", user_id=user_id)
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=body,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                detail = resp.json()["detail"]
                msg = detail["message"] if isinstance(detail, dict) else str(detail)
                assert "special" in msg.lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_apply_username_taken(self, client):
        """POST /users/apply-member → 409 when username already exists (DB constraint)."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_application",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Username already taken."),
                ),
            ):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=_VALID_APPLY_BODY,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                msg = detail["message"] if isinstance(detail, dict) else str(detail)
                assert "username" in msg.lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_apply_missing_fields_422(self, client):
        """POST /users/apply-member with missing fields → 422."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            resp = await client.post(
                "/api/v1/users/apply-member",
                json={"description": "only description"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


class TestApplyDuplicate:
    @pytest.mark.anyio
    async def test_apply_duplicate_pending(self, client):
        """POST /users/apply-member with pending application → 409."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_application",
                    new_callable=AsyncMock,
                    side_effect=ValueError("pending"),
                ),
            ):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=_VALID_APPLY_BODY,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
        finally:
            _clear_overrides()


# ── My application endpoint ──────────────────────────────────


class TestGetMyApplication:
    @pytest.mark.anyio
    async def test_my_application_exists(self, client):
        """GET /users/my-application → 200 with application data."""
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        try:
            _override_auth("GUEST", user_id=user_id)
            with patch(
                "app.services.application.get_my_application",
                new_callable=AsyncMock,
                return_value={
                    "id": uuid.uuid4(),
                    "status": "PENDING",
                    "created_at": now,
                    "reviewed_at": None,
                },
            ):
                resp = await client.get(
                    "/api/v1/users/my-application",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["application"] is not None
                assert data["application"]["status"] == "PENDING"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_my_application_none(self, client):
        """GET /users/my-application → 200 with null when no application."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with patch(
                "app.services.application.get_my_application",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.get(
                    "/api/v1/users/my-application",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["application"] is None
        finally:
            _clear_overrides()


# ── List applications ────────────────────────────────────────


class TestListApplications:
    @pytest.mark.anyio
    async def test_list_applications_admin(self, client):
        """GET /admin/applications → 200 for admin."""
        app_row = _make_application()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.list_applications", new_callable=AsyncMock, return_value=([app_row], 1)
            ):
                resp = await client.get(
                    "/api/v1/admin/applications",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()


class TestListApplicationsFilter:
    @pytest.mark.anyio
    async def test_list_applications_with_status_filter(self, client):
        """GET /admin/applications?status=APPROVED → passes filter."""
        app_row = _make_application()
        app_row["status"] = "APPROVED"

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.list_applications",
                new_callable=AsyncMock,
                return_value=([app_row], 1),
            ) as m:
                resp = await client.get(
                    "/api/v1/admin/applications?status=APPROVED",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                m.assert_called_once_with(status_filter="APPROVED", offset=0, limit=50)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_applications_forbidden_member(self, client):
        """GET /admin/applications → 403 for MEMBER."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/admin/applications",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


# ── Review application ───────────────────────────────────────


class TestReviewApplication:
    @pytest.mark.anyio
    async def test_review_approve(self, client):
        """PUT /admin/applications/{id}/review → 200."""
        app_id = uuid.uuid4()
        app_row = _make_application()
        app_row["status"] = "APPROVED"

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.review_application", new_callable=AsyncMock, return_value=app_row):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "APPROVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "approved" in resp.json()["message"].lower()
        finally:
            _clear_overrides()


class TestReviewReject:
    @pytest.mark.anyio
    async def test_review_reject(self, client):
        """PUT /admin/applications/{id}/review action=REJECTED → 200."""
        app_id = uuid.uuid4()
        app_row = _make_application()
        app_row["status"] = "REJECTED"

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.review_application", new_callable=AsyncMock, return_value=app_row):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "REJECTED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "rejected" in resp.json()["message"].lower()
        finally:
            _clear_overrides()


class TestReviewNotFound:
    @pytest.mark.anyio
    async def test_review_not_found(self, client):
        """PUT /admin/applications/{id}/review → 404 when not found."""
        app_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.review_application", new_callable=AsyncMock, return_value=None):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "APPROVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()


class TestReviewForbiddenMember:
    @pytest.mark.anyio
    async def test_review_forbidden_member(self, client):
        """PUT /admin/applications/{id}/review → 403 for MEMBER."""
        app_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            resp = await client.put(
                f"/api/v1/admin/applications/{app_id}/review",
                json={"action": "APPROVED"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestReviewValueErrorReturns409:
    """review_application ValueError (e.g. user no longer GUEST) must return 409, not 500."""

    @pytest.mark.anyio
    async def test_review_approve_user_no_longer_guest_returns_409(self, client):
        """PUT /admin/applications/{id}/review → 409 when user role already changed."""
        app_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.review_application",
                new_callable=AsyncMock,
                side_effect=ValueError(
                    "User role was not updated: user may have been deleted or is no longer a guest."
                ),
            ):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "APPROVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                detail_str = detail if isinstance(detail, str) else str(detail)
                assert "no longer a guest" in detail_str.lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_review_invalid_action_returns_409(self, client):
        """PUT /admin/applications/{id}/review with invalid action → 409."""
        app_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(
                f"{_EP}.review_application",
                new_callable=AsyncMock,
                side_effect=ValueError("Invalid action: must be one of {'APPROVED', 'REJECTED'}"),
            ):
                resp = await client.put(
                    f"/api/v1/admin/applications/{app_id}/review",
                    json={"action": "APPROVED"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
        finally:
            _clear_overrides()


# ── Repository tests ─────────────────────────────────────────


class TestApplicationInsertTransaction:
    """Verify application_repo.insert wraps check+insert in a transaction."""

    @pytest.mark.anyio
    async def test_insert_no_duplicate_uses_transaction(self, mock_pool, mock_conn):
        """insert() must open a transaction and insert when no pending application exists."""
        from app.repositories.application_repo import insert

        app_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        new_row = {
            "id": app_id,
            "user_id": user_id,
            "description": "I'd like to join",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": now,
        }

        mock_conn.fetchrow = AsyncMock(return_value=new_row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert(app_id, user_id, "I'd like to join")

        assert result is not None
        assert result["id"] == app_id
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_insert_duplicate_returns_none_uses_transaction(self, mock_pool, mock_conn):
        """insert() returns None for duplicate pending application, inside a transaction."""
        from app.repositories.application_repo import insert

        app_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert(app_id, user_id, "Duplicate request")

        assert result is None
        mock_conn.transaction.assert_called_once()


class TestInsertWithUser:
    """insert_with_user creates user + application atomically."""

    @pytest.mark.anyio
    async def test_insert_with_user_success(self, mock_pool, mock_conn):
        """insert_with_user() creates user row then application row."""
        from app.repositories.application_repo import insert_with_user

        app_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        new_row = {
            "id": app_id,
            "user_id": user_id,
            "description": "Join",
            "status": "PENDING",
            "created_at": now,
        }

        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=new_row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert_with_user(
                app_id, user_id, "newuser", "hashed_pw", "New User", "Join"
            )

        assert result is not None
        assert result["id"] == app_id
        mock_conn.execute.assert_called_once()
        sql = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO users" in sql
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.anyio
    async def test_insert_with_user_duplicate_returns_none(self, mock_pool, mock_conn):
        """insert_with_user() returns None if pending application exists."""
        from app.repositories.application_repo import insert_with_user

        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert_with_user(
                uuid.uuid4(), uuid.uuid4(), "user", "hash", "Name", "Desc"
            )

        assert result is None


class TestFindLatestByUser:
    """find_latest_by_user returns most recent application."""

    @pytest.mark.anyio
    async def test_returns_latest(self, mock_pool, mock_conn):
        from app.repositories.application_repo import find_latest_by_user

        now = datetime.now(timezone.utc)
        row = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "description": "x",
            "status": "PENDING",
            "reviewed_at": None,
            "created_at": now,
        }
        mock_conn.fetchrow = AsyncMock(return_value=row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await find_latest_by_user(uuid.uuid4())

        assert result is not None
        assert result["status"] == "PENDING"
        sql = mock_conn.fetchrow.call_args[0][0]
        assert "ORDER BY created_at DESC" in sql

    @pytest.mark.anyio
    async def test_returns_none(self, mock_pool, mock_conn):
        from app.repositories.application_repo import find_latest_by_user

        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await find_latest_by_user(uuid.uuid4())

        assert result is None


# ── Service tests ────────────────────────────────────────────


class TestCreateApplicationService:
    """Service-level create_application tests."""

    @pytest.mark.anyio
    async def test_username_taken_raises_value_error(self):
        """UniqueViolationError on username → ValueError with 'Username already taken'."""
        import asyncpg

        from app.services.application import create_application

        with patch(
            f"{_REPO}.insert_with_user",
            new_callable=AsyncMock,
            side_effect=asyncpg.UniqueViolationError(
                'duplicate key value violates unique constraint "users_username_key"'
            ),
        ):
            with pytest.raises(ValueError, match="Username already taken"):
                await create_application(uuid.uuid4(), "taken", "Passw0rd!", "Name", "Desc")

    @pytest.mark.anyio
    async def test_double_submit_raises_value_error(self):
        """UniqueViolationError on PK → ValueError with 'already submitted'."""
        import asyncpg

        from app.services.application import create_application

        with patch(
            f"{_REPO}.insert_with_user",
            new_callable=AsyncMock,
            side_effect=asyncpg.UniqueViolationError(
                'duplicate key value violates unique constraint "users_pkey"'
            ),
        ):
            with pytest.raises(ValueError, match="already submitted"):
                await create_application(uuid.uuid4(), "user", "Passw0rd!", "Name", "Desc")

    @pytest.mark.anyio
    async def test_duplicate_pending_raises_value_error(self):
        """insert_with_user returning None → ValueError."""
        from app.services.application import create_application

        with patch(
            f"{_REPO}.insert_with_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(ValueError, match="pending"):
                await create_application(uuid.uuid4(), "user", "Passw0rd!", "Name", "Desc")

    @pytest.mark.anyio
    async def test_success(self):
        """Successful application creation."""
        from app.services.application import create_application

        now = datetime.now(timezone.utc)
        row = {"id": uuid.uuid4(), "user_id": uuid.uuid4(), "status": "PENDING", "created_at": now}

        with patch(
            f"{_REPO}.insert_with_user",
            new_callable=AsyncMock,
            return_value=row,
        ):
            result = await create_application(
                uuid.uuid4(), "newuser", "Passw0rd!", "Display", "Description"
            )
            assert result["status"] == "PENDING"


class TestGetMyApplicationService:
    @pytest.mark.anyio
    async def test_delegates_to_repo(self):
        from app.services.application import get_my_application

        user_id = uuid.uuid4()
        with patch(
            f"{_REPO}.find_latest_by_user",
            new_callable=AsyncMock,
            return_value=None,
        ) as m:
            result = await get_my_application(user_id)
            m.assert_called_once_with(user_id)
            assert result is None


# ── Application approval role guard ──────────────────────────


class TestApplicationApprovalRoleGuard:
    """Approve must only promote GUEST users."""

    @pytest.mark.anyio
    async def test_approve_non_guest_raises(self, mock_pool, mock_conn):
        """Approving when user is no longer GUEST raises ValueError."""
        from app.repositories.application_repo import update_status

        app_id = uuid.uuid4()
        reviewer_id = uuid.uuid4()

        app_row = {
            "id": app_id,
            "user_id": uuid.uuid4(),
            "description": "I want to join",
            "status": "APPROVED",
            "reviewed_by": reviewer_id,
            "reviewed_at": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=app_row)
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            with pytest.raises(ValueError, match="no longer a guest"):
                await update_status(app_id, reviewer_id, "APPROVED")

    @pytest.mark.anyio
    async def test_approve_guest_succeeds(self, mock_pool, mock_conn):
        """Approving a GUEST user succeeds normally."""
        from app.repositories.application_repo import update_status

        app_id = uuid.uuid4()
        reviewer_id = uuid.uuid4()

        app_row = {
            "id": app_id,
            "user_id": uuid.uuid4(),
            "description": "I want to join",
            "status": "APPROVED",
            "reviewed_by": reviewer_id,
            "reviewed_at": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=app_row)
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await update_status(app_id, reviewer_id, "APPROVED")
        assert result is not None

    @pytest.mark.anyio
    async def test_reject_does_not_update_user_role(self, mock_pool, mock_conn):
        """Rejecting an application should not attempt user role update."""
        from app.repositories.application_repo import update_status

        app_id = uuid.uuid4()
        reviewer_id = uuid.uuid4()

        app_row = {
            "id": app_id,
            "user_id": uuid.uuid4(),
            "description": "I want to join",
            "status": "REJECTED",
            "reviewed_by": reviewer_id,
            "reviewed_at": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=app_row)
        mock_conn.execute = AsyncMock()

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await update_status(app_id, reviewer_id, "REJECTED")
        assert result is not None
        mock_conn.execute.assert_not_called()


# ── Review action validation ─────────────────────────────────


class TestReviewApplicationActionValidation:
    """review_application must reject invalid action strings."""

    @pytest.mark.anyio
    async def test_invalid_action_raises_value_error(self):
        from app.services.application import review_application

        with pytest.raises(ValueError, match="Invalid action"):
            await review_application(uuid.uuid4(), uuid.uuid4(), "INVALID")

    @pytest.mark.anyio
    async def test_approved_action_passes_validation(self):
        from app.services.application import review_application

        app_row = _make_application()
        app_row["status"] = "APPROVED"

        with (
            patch(f"{_REPO}.update_status", new_callable=AsyncMock, return_value=app_row),
            patch("app.services.application.emit", new_callable=AsyncMock),
            patch("app.services.auth.revoke_user_sessions", new_callable=AsyncMock),
        ):
            result = await review_application(uuid.uuid4(), uuid.uuid4(), "APPROVED")
            assert result is not None
            assert result["status"] == "APPROVED"

    @pytest.mark.anyio
    async def test_rejected_action_passes_validation(self):
        from app.services.application import review_application

        app_row = _make_application()
        app_row["status"] = "REJECTED"

        with (
            patch(f"{_REPO}.update_status", new_callable=AsyncMock, return_value=app_row),
            patch("app.services.application.emit", new_callable=AsyncMock),
        ):
            result = await review_application(uuid.uuid4(), uuid.uuid4(), "REJECTED")
            assert result is not None
            assert result["status"] == "REJECTED"


# ── Re-apply after rejection ────────────────────────────────


class TestReApplyAfterRejection:
    """Guest re-applies after previous rejection — ON CONFLICT updates user record."""

    @pytest.mark.anyio
    async def test_reapply_after_rejection_succeeds(self, mock_pool, mock_conn):
        """insert_with_user() succeeds on re-apply: ON CONFLICT updates GUEST user."""
        from app.repositories.application_repo import insert_with_user

        app_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        new_row = {
            "id": app_id,
            "user_id": user_id,
            "description": "Please reconsider",
            "status": "PENDING",
            "created_at": now,
        }

        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=new_row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert_with_user(
                app_id, user_id, "newuser2", "hashed_pw2", "Updated Name", "Please reconsider"
            )

        assert result is not None
        assert result["id"] == app_id
        assert result["status"] == "PENDING"
        # Verify the INSERT uses ON CONFLICT
        sql = mock_conn.execute.call_args[0][0]
        assert "ON CONFLICT (id) DO UPDATE" in sql
        assert "WHERE users.role = 'GUEST'" in sql

    @pytest.mark.anyio
    async def test_reapply_while_pending_fails(self, mock_pool, mock_conn):
        """insert_with_user() returns None when a PENDING application already exists."""
        from app.repositories.application_repo import insert_with_user

        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert_with_user(
                uuid.uuid4(), uuid.uuid4(), "user", "hash", "Name", "Desc"
            )

        assert result is None

    @pytest.mark.anyio
    async def test_reapply_while_pending_endpoint_returns_409(self, client):
        """POST /users/apply-member while PENDING → 409 via service ValueError."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_application",
                    new_callable=AsyncMock,
                    side_effect=ValueError("You already have a pending application."),
                ),
            ):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=_VALID_APPLY_BODY,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                detail = resp.json()["detail"]
                msg = detail["message"] if isinstance(detail, dict) else str(detail)
                assert "pending" in msg.lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_reapply_after_rejection_endpoint_succeeds(self, client):
        """POST /users/apply-member after rejection → 200 (ON CONFLICT handles user upsert)."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            now = datetime.now(timezone.utc)
            row = {
                "id": uuid.uuid4(),
                "user_id": uuid.UUID(user_id),
                "status": "PENDING",
                "created_at": now,
            }
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_application",
                    new_callable=AsyncMock,
                    return_value=row,
                ),
            ):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json=_VALID_APPLY_BODY,
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "submitted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()


# ── _app_to_response direct dict access ─────────────────────


class TestAppToResponseDirectAccess:
    """_app_to_response uses direct dict access for guaranteed fields."""

    def test_missing_username_raises_key_error(self):
        """_app_to_response raises KeyError when username is missing (not silently defaulting)."""
        from app.api.v1.endpoints.applications import _app_to_response

        app = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            # "username" intentionally omitted
            "display_name": "Test",
            "description": "desc",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        with pytest.raises(KeyError):
            _app_to_response(app)

    def test_missing_display_name_raises_key_error(self):
        """_app_to_response raises KeyError when display_name is missing."""
        from app.api.v1.endpoints.applications import _app_to_response

        app = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "username": "test",
            # "display_name" intentionally omitted
            "description": "desc",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        with pytest.raises(KeyError):
            _app_to_response(app)

    def test_complete_dict_succeeds(self):
        """_app_to_response succeeds with all fields present."""
        from app.api.v1.endpoints.applications import _app_to_response

        app = _make_application()
        result = _app_to_response(app)
        assert result.username == "guest1"
        assert result.display_name == "Guest User"
