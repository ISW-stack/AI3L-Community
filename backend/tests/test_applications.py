"""Tests for applications endpoints.

apply success, non-guest rejected, list admin, review approve.
Also covers atomic check+insert transaction safety in application_repo.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.applications"
_REPO = "app.repositories.application_repo"


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


class TestApplyMembership:
    @pytest.mark.anyio
    async def test_apply_success(self, client):
        """POST /users/apply-member → 200 for GUEST."""
        user_id = str(uuid.uuid4())

        try:
            _override_auth("GUEST", user_id=user_id)
            with patch(f"{_EP}.create_application", new_callable=AsyncMock):
                resp = await client.post(
                    "/api/v1/users/apply-member",
                    json={"description": "I'd like to join"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "submitted" in resp.json()["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_non_guest_rejected(self, client):
        """POST /users/apply-member → 400 for non-GUEST."""
        try:
            _override_auth("MEMBER")
            resp = await client.post(
                "/api/v1/users/apply-member",
                json={"description": "Want to join"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 400
        finally:
            _clear_overrides()


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

        # fetchval returns 0 (no existing pending), fetchrow returns the new row
        mock_conn.fetchval = AsyncMock(return_value=0)
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

        # fetchval returns 1 (existing pending application)
        mock_conn.fetchval = AsyncMock(return_value=1)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            result = await insert(app_id, user_id, "Duplicate request")

        assert result is None
        # INSERT should NOT have been called
        mock_conn.fetchrow.assert_not_called()
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_insert_concurrent_only_one_succeeds(self, mock_pool, mock_conn):
        """Simulate concurrent inserts: second call sees pending and returns None."""
        import asyncio

        from app.repositories.application_repo import insert

        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        call_count = 0

        async def fetchval_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call: no pending; second call: sees the first one as pending
            return 0 if call_count == 1 else 1

        new_row = {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "description": "Join request",
            "status": "PENDING",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": now,
        }

        mock_conn.fetchval = AsyncMock(side_effect=fetchval_side_effect)
        mock_conn.fetchrow = AsyncMock(return_value=new_row)

        with patch(f"{_REPO}.get_pool", return_value=mock_pool):
            results = await asyncio.gather(
                insert(uuid.uuid4(), user_id, "Join request"),
                insert(uuid.uuid4(), user_id, "Join request"),
            )

        # One result should be non-None and one None
        non_none = [r for r in results if r is not None]
        none_results = [r for r in results if r is None]
        assert len(non_none) == 1
        assert len(none_results) == 1
        assert mock_conn.transaction.call_count == 2
