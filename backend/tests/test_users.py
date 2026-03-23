"""Tests for app.services.user + app.api.v1.endpoints.users."""

import uuid
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from tests.conftest import make_user_dict

_UEP = "app.api.v1.endpoints.users"


# ── Service layer tests ─────────────────────────────────────────────


class TestCreateUser:
    @patch("app.repositories.user_repo.get_pool")
    @patch("app.services.user.async_hash_password", new_callable=AsyncMock, return_value="hashed")
    async def test_create_user(self, mock_hash, mock_get_pool, mock_pool, mock_conn):
        from app.services.user import create_user

        user = make_user_dict(username="newuser")
        mock_conn.fetchrow.return_value = user
        mock_get_pool.return_value = mock_pool

        result = await create_user("newuser", "Password1", display_name="New")
        assert result["username"] == "newuser"
        mock_conn.fetchrow.assert_called_once()


class TestGetUserById:
    @patch("app.repositories.user_repo.get_pool")
    async def test_get_user_by_id_found(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.user import get_user_by_id

        user = make_user_dict()
        mock_conn.fetchrow.return_value = user
        mock_get_pool.return_value = mock_pool

        result = await get_user_by_id(user["id"])
        assert result is not None
        assert result["id"] == user["id"]

    @patch("app.repositories.user_repo.get_pool")
    async def test_get_user_by_id_not_found(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.user import get_user_by_id

        mock_conn.fetchrow.return_value = None
        mock_get_pool.return_value = mock_pool

        result = await get_user_by_id(uuid.uuid4())
        assert result is None


class TestUpdateUserProfile:
    @patch("app.repositories.user_repo.get_pool")
    async def test_update_user_profile(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.user import update_user_profile

        updated = make_user_dict(username="alice")
        updated["display_name"] = "Alice Updated"
        mock_conn.fetchrow.return_value = updated
        mock_get_pool.return_value = mock_pool

        result = await update_user_profile(updated["id"], display_name="Alice Updated")
        assert result["display_name"] == "Alice Updated"

    @patch("app.repositories.user_repo.get_pool")
    async def test_update_profile_clears_bio_with_none(self, mock_get_pool, mock_pool, mock_conn):
        """N-B10: Passing bio=None should SET bio to NULL (clear the field)."""
        from app.services.user import update_user_profile

        user = make_user_dict(username="alice")
        user["bio"] = None
        mock_conn.fetchrow.return_value = user
        mock_get_pool.return_value = mock_pool

        result = await update_user_profile(user["id"], bio=None)
        assert result is not None
        # Verify fetchrow was called (UPDATE query, not just find_by_id)
        mock_conn.fetchrow.assert_called_once()
        # The SQL should include bio = $1 with None value
        call_args = mock_conn.fetchrow.call_args
        query = call_args[0][0]
        assert "bio" in query
        assert "UPDATE" in query

    @patch("app.repositories.user_repo.get_pool")
    async def test_update_profile_clears_multiple_fields(self, mock_get_pool, mock_pool, mock_conn):
        """N-B10: Clearing bio, affiliation, orcid simultaneously."""
        from app.services.user import update_user_profile

        user = make_user_dict(username="alice")
        user["bio"] = None
        user["affiliation"] = None
        user["orcid"] = None
        mock_conn.fetchrow.return_value = user
        mock_get_pool.return_value = mock_pool

        result = await update_user_profile(user["id"], bio=None, affiliation=None, orcid=None)
        assert result is not None
        call_args = mock_conn.fetchrow.call_args
        query = call_args[0][0]
        assert "bio" in query
        assert "affiliation" in query
        assert "orcid" in query

    @patch("app.repositories.user_repo.get_pool")
    async def test_update_profile_via_repo_no_fields_returns_existing(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """N-B10: Repo update_profile with no kwargs returns existing user (SELECT)."""
        from app.repositories.user_repo import update_profile

        user = make_user_dict(username="alice")
        mock_conn.fetchrow.return_value = user
        mock_get_pool.return_value = mock_pool

        result = await update_profile(user["id"])
        assert result is not None
        # No fields provided → should call find_by_id (SELECT), not UPDATE
        call_args = mock_conn.fetchrow.call_args
        query = call_args[0][0]
        assert "SELECT" in query


class TestBanUser:
    @patch("app.services.user.emit", new_callable=AsyncMock)
    @patch("app.services.auth.revoke_user_sessions", new_callable=AsyncMock)
    @patch("app.repositories.user_repo.get_pool")
    async def test_ban_user(self, mock_get_pool, mock_revoke, mock_emit, mock_pool, mock_conn):
        from app.services.user import ban_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await ban_user(uuid.uuid4(), "spam")
        assert result is True
        mock_revoke.assert_called_once()


class TestUnbanUser:
    @patch("app.repositories.user_repo.get_pool")
    async def test_unban_user(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.user import unban_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await unban_user(uuid.uuid4())
        assert result is True

    @patch("app.repositories.user_repo.get_pool")
    async def test_unban_user_not_found(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.user import unban_user

        mock_conn.execute.return_value = "UPDATE 0"
        mock_get_pool.return_value = mock_pool

        result = await unban_user(uuid.uuid4())
        assert result is False


class TestAnonymizeUser:
    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_user(self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        result = await anonymize_user(uuid.uuid4())
        assert result["anonymized"] is True


# ── Endpoint tests ───────────────────────────────────────────────────


def _override_user(role: str, user_id: str | None = None):
    """Create a dependency override for get_current_user."""
    if user_id is None:
        user_id = str(uuid.uuid4())
    payload = {"sub": user_id, "role": role, "jti": "jti-test"}
    return payload


class TestBanEndpoint:
    async def test_ban_endpoint_super_admin_only(self, client: AsyncClient):
        """Non-SUPER_ADMIN should get 403."""
        from app.core.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: _override_user("ADMIN")
        try:
            target_id = uuid.uuid4()
            resp = await client.post(
                f"/api/v1/users/{target_id}/ban",
                json={"reason": "spam"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch(f"{_UEP}.ban_user", new_callable=AsyncMock, return_value=True)
    async def test_ban_endpoint_cannot_ban_self(self, mock_ban, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        app.dependency_overrides[get_current_user] = lambda: _override_user("SUPER_ADMIN", user_id)
        try:
            resp = await client.post(
                f"/api/v1/users/{user_id}/ban",
                json={"reason": "test"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch(f"{_UEP}.ban_user", new_callable=AsyncMock, return_value=True)
    async def test_ban_endpoint_success(self, mock_ban, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())
        app.dependency_overrides[get_current_user] = lambda: _override_user("SUPER_ADMIN", user_id)
        try:
            resp = await client.post(
                f"/api/v1/users/{target_id}/ban",
                json={"reason": "spam"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestUnbanEndpoint:
    @patch(f"{_UEP}.unban_user", new_callable=AsyncMock, return_value=True)
    async def test_unban_endpoint(self, mock_unban, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())
        app.dependency_overrides[get_current_user] = lambda: _override_user("SUPER_ADMIN", user_id)
        try:
            resp = await client.post(
                f"/api/v1/users/{target_id}/unban",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestConsentEndpoint:
    @patch("app.api.v1.endpoints.users.create_consent", new_callable=AsyncMock)
    async def test_consent_endpoint(self, mock_consent, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        payload = _override_user("MEMBER")
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post(
                "/api/v1/users/me/consent",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            mock_consent.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
