"""Tests for SIGs endpoints — list, create, get, not-found, remove member, assign sub-admin, list members, list posts."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.sigs"
_SVC = "app.services.sig"


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


class TestListSigs:
    @pytest.mark.anyio
    async def test_list_sigs(self, client, mock_pool, mock_conn):
        """GET /sigs → 200."""
        now = datetime.now(timezone.utc)
        sig = {
            "id": uuid.uuid4(), "name": "Test SIG", "description": "Desc",
            "created_by": uuid.uuid4(), "member_count": 1, "is_deleted": False,
            "created_at": now, "updated_at": now, "creator_display_name": "Creator",
        }
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[sig])

        try:
            _override_auth("MEMBER")
            with patch(f"{_SVC}.get_pool", return_value=mock_pool):
                resp = await client.get(
                    "/api/v1/sigs",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()


class TestCreateSig:
    @pytest.mark.anyio
    async def test_create_sig(self, client, mock_pool, mock_conn):
        """POST /sigs → 201."""
        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        sig_row = {
            "id": sig_id, "name": "New SIG", "description": "Desc",
            "created_by": uuid.uuid4(), "member_count": 1, "is_deleted": False,
            "created_at": now, "updated_at": now,
        }
        creator_row = {"display_name": "Creator"}

        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, creator_row])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        try:
            _override_auth("ADMIN")
            with patch(f"{_SVC}.get_pool", return_value=mock_pool):
                resp = await client.post(
                    "/api/v1/sigs",
                    json={"name": "New SIG", "description": "Desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["name"] == "New SIG"
        finally:
            _clear_overrides()


class TestGetSig:
    @pytest.mark.anyio
    async def test_get_sig(self, client, mock_pool, mock_conn):
        """GET /sigs/{id} → 200."""
        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        sig_row = {
            "id": sig_id, "name": "Test SIG", "description": "Desc",
            "created_by": uuid.uuid4(), "member_count": 3, "is_deleted": False,
            "created_at": now, "updated_at": now, "creator_display_name": "Creator",
        }

        mock_conn.fetchrow = AsyncMock(return_value=sig_row)

        try:
            _override_auth("MEMBER")
            with patch(f"{_SVC}.get_pool", return_value=mock_pool):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["name"] == "Test SIG"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_sig_not_found(self, client, mock_pool, mock_conn):
        """GET /sigs/{id} → 404 when not found."""
        sig_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        try:
            _override_auth("MEMBER")
            with patch(f"{_SVC}.get_pool", return_value=mock_pool):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()


class TestRemoveMember:
    @pytest.mark.anyio
    async def test_remove_member(self, client):
        """DELETE /sigs/{id}/members/{uid} → 200 for admin."""
        sig_id = uuid.uuid4()
        target_user = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.remove_member", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/{target_user}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestAssignSubAdmin:
    @pytest.mark.anyio
    async def test_assign_sub_admin(self, client):
        """POST /sigs/{id}/sub-admin → 200."""
        sig_id = uuid.uuid4()
        target_user = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        member = {
            "id": str(uuid.uuid4()),
            "sig_id": str(sig_id),
            "user_id": target_user,
            "role": "SUB_ADMIN",
            "display_name": "User1",
            "username": "user1",
            "created_at": now,
        }

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.assign_sub_admin", new_callable=AsyncMock, return_value=member):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestListMembers:
    @pytest.mark.anyio
    async def test_list_members(self, client):
        """GET /sigs/{id}/members → 200."""
        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc).isoformat()
        member = {
            "id": str(uuid.uuid4()),
            "sig_id": str(sig_id),
            "user_id": str(uuid.uuid4()),
            "role": "MEMBER",
            "display_name": "User1",
            "username": "user1",
            "created_at": now,
        }

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.list_sig_members", new_callable=AsyncMock, return_value=([member], 1)):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/members",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
        finally:
            _clear_overrides()


class TestListSigPosts:
    @pytest.mark.anyio
    async def test_list_sig_posts(self, client):
        """GET /sigs/{id}/posts → 200."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.list_posts", new_callable=AsyncMock, return_value=([], 0, 0)):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/posts",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 0
        finally:
            _clear_overrides()
