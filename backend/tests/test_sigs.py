"""Tests for SIGs endpoints.

list, create, get, not-found, remove member, assign sub-admin, demote sub-admin,
list members, list posts. Also covers update_sig transaction safety.
"""

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
            "id": uuid.uuid4(),
            "name": "Test SIG",
            "description": "Desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Creator",
        }
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[sig])

        try:
            _override_auth("MEMBER")
            with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
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
            "id": sig_id,
            "name": "New SIG",
            "description": "Desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        creator_row = {"display_name": "Creator"}

        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, creator_row])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch("app.services.sig.get_pool", return_value=mock_pool),
            ):
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
            "id": sig_id,
            "name": "Test SIG",
            "description": "Desc",
            "created_by": uuid.uuid4(),
            "member_count": 3,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Creator",
        }

        mock_conn.fetchrow = AsyncMock(return_value=sig_row)

        try:
            _override_auth("MEMBER")
            with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
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
            with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
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
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.remove_member", new_callable=AsyncMock, return_value=True),
            ):
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
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.assign_sub_admin", new_callable=AsyncMock, return_value=member),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestDemoteSubAdmin:
    @pytest.mark.anyio
    async def test_demote_sub_admin_success(self, client):
        """POST /sigs/{id}/sub-admin/demote → 200 for admin."""
        sig_id = uuid.uuid4()
        target_user = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        member = {
            "id": str(uuid.uuid4()),
            "sig_id": str(sig_id),
            "user_id": target_user,
            "role": "MEMBER",
            "display_name": "User1",
            "username": "user1",
            "created_at": now,
        }

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.demote_sub_admin", new_callable=AsyncMock, return_value=member),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin/demote",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["role"] == "MEMBER"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_demote_sub_admin_forbidden_for_regular_member(self, client):
        """POST /sigs/{id}/sub-admin/demote → 403 for non-admin SIG member."""
        sig_id = uuid.uuid4()
        target_user = str(uuid.uuid4())

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.demote_sub_admin",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Not authorized."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin/demote",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_demote_sub_admin_not_sub_admin(self, client):
        """POST /sigs/{id}/sub-admin/demote → 400 when target is not a sub-admin."""
        sig_id = uuid.uuid4()
        target_user = str(uuid.uuid4())

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.demote_sub_admin",
                    new_callable=AsyncMock,
                    side_effect=ValueError("User is not a sub-admin."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin/demote",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_demote_sub_admin_cannot_demote_owner(self, client):
        """POST /sigs/{id}/sub-admin/demote → 400 when target is the SIG owner."""
        sig_id = uuid.uuid4()
        target_user = str(uuid.uuid4())

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.demote_sub_admin",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Cannot demote the SIG owner/creator."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin/demote",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "owner" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_demote_sub_admin_sig_admin_allowed(self, client):
        """POST /sigs/{id}/sub-admin/demote → 200 for SIG ADMIN (owner)."""
        sig_id = uuid.uuid4()
        target_user = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        member = {
            "id": str(uuid.uuid4()),
            "sig_id": str(sig_id),
            "user_id": target_user,
            "role": "MEMBER",
            "display_name": "User1",
            "username": "user1",
            "created_at": now,
        }

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.demote_sub_admin",
                    new_callable=AsyncMock,
                    return_value=member,
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin/demote",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["role"] == "MEMBER"
        finally:
            _clear_overrides()


class TestAssignSubAdminNonMember:
    """Bug #1: Non-member should not be assignable as sub-admin."""

    @pytest.mark.anyio
    async def test_assign_sub_admin_non_member_raises(self, mock_pool, mock_conn):
        """assign_sub_admin raises ValueError when user is not a SIG member."""
        from app.services.sig import assign_sub_admin

        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        # get_member_role_in_conn returns None → not a member
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(ValueError, match="must be a member"):
                await assign_sub_admin(
                    sig_id,
                    user_id,
                    caller_id=str(uuid.uuid4()),
                    caller_role="ADMIN",
                )


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
            with patch(
                f"{_EP}.list_sig_members", new_callable=AsyncMock, return_value=([member], 1)
            ):
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
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={"posts": [], "total": 0, "total_pages": 0},
            ):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/posts",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 0
        finally:
            _clear_overrides()


class TestUpdateSigTransaction:
    """Verify update_sig wraps the read-then-update in a single transaction."""

    @pytest.mark.anyio
    async def test_update_sig_uses_transaction(self, mock_pool, mock_conn):
        """update_sig must open a transaction before reading current values."""
        from app.services.sig import update_sig

        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        sig_row = {
            "id": sig_id,
            "name": "Updated SIG",
            "description": "New desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Creator",
        }

        # First fetchrow returns current values (SELECT), second returns updated row (UPDATE CTE)
        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, sig_row])

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            result = await update_sig(sig_id, name="Updated SIG")

        assert result is not None
        assert result["name"] == "Updated SIG"
        # transaction() must have been entered
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_update_sig_not_found_returns_none(self, mock_pool, mock_conn):
        """update_sig returns None when the SIG does not exist, transaction still used."""
        from app.services.sig import update_sig

        sig_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            result = await update_sig(sig_id, name="Ghost SIG")

        assert result is None
        mock_conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_update_sig_concurrent_transaction_isolation(self, mock_pool, mock_conn):
        """Simulate two concurrent updates: each must use its own transaction."""
        import asyncio

        from app.services.sig import update_sig

        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        sig_row = {
            "id": sig_id,
            "name": "Concurrent SIG",
            "description": "desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Creator",
        }

        # Each call to update_sig gets its own mock_pool/mock_conn invocation
        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, sig_row, sig_row, sig_row])

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            results = await asyncio.gather(
                update_sig(sig_id, name="Concurrent SIG"),
                update_sig(sig_id, name="Concurrent SIG"),
            )

        assert all(r is not None for r in results)
        # transaction() called once per update_sig call (2 total)
        assert mock_conn.transaction.call_count == 2


# ── Bug fix: sole admin protection ─────────────────────────────────


class TestRemoveMemberSoleAdmin:
    """Bug fix: remove_member must prevent removing the last admin."""

    @pytest.mark.anyio
    async def test_remove_last_admin_raises(self, mock_pool, mock_conn):
        """remove_member raises ValueError when target is the sole admin."""
        from app.services.sig import remove_member

        sig_id = uuid.uuid4()
        admin_user_id = str(uuid.uuid4())
        caller_id = str(uuid.uuid4())

        admin_row = {"id": uuid.uuid4()}
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                {"role": "ADMIN"},  # target member role
            ]
        )
        # count_admins returns 1 (sole admin)
        mock_conn.fetch = AsyncMock(return_value=[admin_row])

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(ValueError, match="last admin"):
                await remove_member(
                    sig_id,
                    admin_user_id,
                    caller_id=caller_id,
                    caller_role="ADMIN",
                )

    @pytest.mark.anyio
    async def test_remove_non_admin_succeeds(self, mock_pool, mock_conn):
        """remove_member succeeds when target is a regular MEMBER."""
        from app.services.sig import remove_member

        sig_id = uuid.uuid4()
        member_user_id = str(uuid.uuid4())
        caller_id = str(uuid.uuid4())

        mock_conn.fetchrow = AsyncMock(return_value={"role": "MEMBER"})
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            result = await remove_member(
                sig_id,
                member_user_id,
                caller_id=caller_id,
                caller_role="ADMIN",
            )
        assert result is True

    @pytest.mark.anyio
    async def test_remove_admin_when_multiple_admins(self, mock_pool, mock_conn):
        """remove_member succeeds when target is ADMIN but others exist."""
        from app.services.sig import remove_member

        sig_id = uuid.uuid4()
        admin_user_id = str(uuid.uuid4())
        caller_id = str(uuid.uuid4())

        mock_conn.fetchrow = AsyncMock(return_value={"role": "ADMIN"})
        # count_admins returns 2 admins
        mock_conn.fetch = AsyncMock(return_value=[{"id": uuid.uuid4()}, {"id": uuid.uuid4()}])
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            result = await remove_member(
                sig_id,
                admin_user_id,
                caller_id=caller_id,
                caller_role="ADMIN",
            )
        assert result is True


class TestRemoveMemberSoleAdminEndpoint:
    """Endpoint: DELETE /sigs/{id}/members/{uid} → 400 for sole admin."""

    @pytest.mark.anyio
    async def test_remove_sole_admin_returns_400(self, client):
        sig_id = uuid.uuid4()
        target_user = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.remove_member",
                    new_callable=AsyncMock,
                    side_effect=ValueError(
                        "Cannot remove: this user is the last admin of the SIG."
                    ),
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/{target_user}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "last admin" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()


# ── Bug fix: TOCTOU — service-level authorization ──────────────────


class TestServiceLayerAuthorization:
    """Bug fix: authorization checked inside transaction (TOCTOU)."""

    @pytest.mark.anyio
    async def test_remove_member_unauthorized_caller(self, mock_pool, mock_conn):
        """remove_member raises PermissionError for non-admin caller."""
        from app.services.sig import remove_member

        sig_id = uuid.uuid4()
        target_id = str(uuid.uuid4())
        caller_id = str(uuid.uuid4())

        # Caller's SIG role is MEMBER (not ADMIN)
        mock_conn.fetchrow = AsyncMock(return_value={"role": "MEMBER"})

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(PermissionError, match="Not authorized"):
                await remove_member(
                    sig_id,
                    target_id,
                    caller_id=caller_id,
                    caller_role="MEMBER",
                )

    @pytest.mark.anyio
    async def test_assign_sub_admin_unauthorized_caller(self, mock_pool, mock_conn):
        """assign_sub_admin raises PermissionError for non-admin caller."""
        from app.services.sig import assign_sub_admin

        sig_id = uuid.uuid4()
        target_id = str(uuid.uuid4())
        caller_id = str(uuid.uuid4())

        mock_conn.fetchrow = AsyncMock(return_value={"role": "MEMBER"})

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(PermissionError, match="Not authorized"):
                await assign_sub_admin(
                    sig_id,
                    target_id,
                    caller_id=caller_id,
                    caller_role="MEMBER",
                )

    @pytest.mark.anyio
    async def test_demote_sub_admin_unauthorized_caller(self, mock_pool, mock_conn):
        """demote_sub_admin raises PermissionError for non-admin caller."""
        from app.services.sig import demote_sub_admin

        sig_id = uuid.uuid4()
        target_id = str(uuid.uuid4())
        caller_id = str(uuid.uuid4())

        mock_conn.fetchrow = AsyncMock(return_value={"role": "MEMBER"})

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            with pytest.raises(PermissionError, match="Not authorized"):
                await demote_sub_admin(
                    sig_id,
                    target_id,
                    caller_id=caller_id,
                    caller_role="MEMBER",
                )

    @pytest.mark.anyio
    async def test_global_admin_bypasses_sig_role_check(self, mock_pool, mock_conn):
        """Global ADMIN can remove members without being a SIG admin."""
        from app.services.sig import remove_member

        sig_id = uuid.uuid4()
        target_id = str(uuid.uuid4())
        caller_id = str(uuid.uuid4())

        mock_conn.fetchrow = AsyncMock(return_value={"role": "MEMBER"})
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        with patch(f"{_SVC}.get_pool", return_value=mock_pool):
            result = await remove_member(
                sig_id,
                target_id,
                caller_id=caller_id,
                caller_role="ADMIN",
            )
        assert result is True

    @pytest.mark.anyio
    async def test_remove_member_permission_error_403(self, client):
        """DELETE /sigs/{id}/members/{uid} → 403 on PermissionError."""
        sig_id = uuid.uuid4()
        target_user = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.remove_member",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Not authorized."),
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/{target_user}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_assign_sub_admin_permission_error_403(self, client):
        """POST /sigs/{id}/sub-admin → 403 on PermissionError."""
        sig_id = uuid.uuid4()
        target_user = str(uuid.uuid4())

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.assign_sub_admin",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Not authorized."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_demote_sub_admin_permission_error_403(self, client):
        """POST /sigs/{id}/sub-admin/demote → 403 on PermissionError."""
        sig_id = uuid.uuid4()
        target_user = str(uuid.uuid4())

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.demote_sub_admin",
                    new_callable=AsyncMock,
                    side_effect=PermissionError("Not authorized."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/sub-admin/demote",
                    json={"user_id": target_user},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestSigJoinRateLimit:
    @pytest.mark.anyio
    async def test_join_sig_rate_limited(self, client):
        """POST /sigs/{id}/members/me → 429 when rate limited."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_leave_sig_rate_limited(self, client):
        """DELETE /sigs/{id}/members/me → 429 when rate limited."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestSigCrudRateLimit:
    @pytest.mark.anyio
    async def test_create_sig_rate_limited(self, client):
        """POST /sigs → 429 when rate limited."""
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    "/api/v1/sigs",
                    json={"name": "New SIG", "description": "Desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestSigManageRateLimit:
    @pytest.mark.anyio
    async def test_remove_member_rate_limited(self, client):
        """DELETE /sigs/{id}/members/{uid} → 429 when rate limited."""
        sig_id = uuid.uuid4()
        target_user = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/{target_user}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestJoinSigErrors:
    @pytest.mark.anyio
    async def test_join_sig_already_member_returns_409(self, client):
        """POST /sigs/{id}/members/me → 409 when already a member."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.join_sig",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Already a member of this SIG."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_join_sig_not_found_returns_404(self, client):
        """POST /sigs/{id}/members/me → 404 when SIG not found."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.join_sig",
                    new_callable=AsyncMock,
                    side_effect=ValueError("SIG not found."),
                ),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_join_sig_success_returns_201(self, client):
        """POST /sigs/{id}/members/me → 201 on success."""
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
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.join_sig", new_callable=AsyncMock, return_value=member),
            ):
                resp = await client.post(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
        finally:
            _clear_overrides()


class TestLeaveSigErrors:
    @pytest.mark.anyio
    async def test_leave_sig_last_admin_returns_422(self, client):
        """DELETE /sigs/{id}/members/me → 422 when last admin tries to leave."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.leave_sig",
                    new_callable=AsyncMock,
                    side_effect=ValueError(
                        "Cannot leave: you are the last admin of this SIG."
                    ),
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_leave_sig_not_member_returns_404(self, client):
        """DELETE /sigs/{id}/members/me → 404 when not a member."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.leave_sig", new_callable=AsyncMock, return_value=False),
            ):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_leave_sig_success(self, client):
        """DELETE /sigs/{id}/members/me → 200 on success."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.leave_sig", new_callable=AsyncMock, return_value=True),
            ):
                resp = await client.delete(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestCreateSigDuplicateName:
    @pytest.mark.anyio
    async def test_create_sig_duplicate_name_returns_409(self, client):
        """POST /sigs → 409 when SIG name already exists."""
        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_sig",
                    new_callable=AsyncMock,
                    side_effect=ValueError("A SIG with this name already exists."),
                ),
            ):
                resp = await client.post(
                    "/api/v1/sigs",
                    json={"name": "Duplicate SIG", "description": "Desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
        finally:
            _clear_overrides()


class TestSoftDeleteSig:
    @pytest.mark.anyio
    async def test_soft_delete_sig_updates_sig_members_not_deletes(self, mock_pool, mock_conn):
        """soft_delete() must UPDATE sig_members.is_deleted = true (not DELETE)."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()

        execute_calls: list[str] = []

        async def _execute(sql: str, *args: object) -> str:
            execute_calls.append(sql.strip())
            if "UPDATE sigs" in sql:
                return "UPDATE 1"
            return "UPDATE 5"

        mock_conn.execute = _execute

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            result = await sig_repo.soft_delete(sig_id)

        assert result is True

        sig_members_calls = [c for c in execute_calls if "sig_members" in c.lower()]
        assert len(sig_members_calls) == 1
        assert sig_members_calls[0].startswith("UPDATE sig_members SET is_deleted = true")
        # Ensure there is no DELETE on sig_members
        for call in execute_calls:
            if "sig_members" in call.lower():
                assert not call.upper().startswith("DELETE"), (
                    f"Expected UPDATE but got DELETE: {call}"
                )


class TestGetMySigMembership:
    @pytest.mark.anyio
    async def test_get_my_membership_returns_role(self, client):
        """GET /sigs/{id}/members/me → 200 with role."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.get_member_role",
                new_callable=AsyncMock,
                return_value="ADMIN",
            ):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["role"] == "ADMIN"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_my_membership_not_member_returns_404(self, client):
        """GET /sigs/{id}/members/me → 404 when not a member."""
        sig_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.get_member_role",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/members/me",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
        finally:
            _clear_overrides()
