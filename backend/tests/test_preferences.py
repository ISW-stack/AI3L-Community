"""Tests for user preferences endpoints — GET and PUT /users/me/preferences."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_EP_PREFS = "app.api.v1.endpoints.preferences"


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


class TestGetPreferences:
    @pytest.mark.anyio
    async def test_returns_defaults_when_no_row(self, client):
        """GET /users/me/preferences → 200 with defaults when no prefs saved."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_PREFS}.get_user_preferences",
                new_callable=AsyncMock,
                return_value={
                    "theme": "light",
                    "notify_mentions": True,
                    "notify_replies": True,
                    "notify_sig_posts": True,
                },
            ):
                resp = await client.get(
                    "/api/v1/users/me/preferences",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["theme"] == "light"
                assert data["notify_mentions"] is True
                assert data["notify_replies"] is True
                assert data["notify_sig_posts"] is True
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_returns_saved_values(self, client):
        """GET /users/me/preferences → 200 with saved values."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP_PREFS}.get_user_preferences",
                new_callable=AsyncMock,
                return_value={
                    "theme": "dark",
                    "notify_mentions": False,
                    "notify_replies": True,
                    "notify_sig_posts": False,
                },
            ):
                resp = await client.get(
                    "/api/v1/users/me/preferences",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["theme"] == "dark"
                assert data["notify_mentions"] is False
                assert data["notify_sig_posts"] is False
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_unauthenticated_returns_401(self, client):
        """GET /users/me/preferences without auth → 401."""
        resp = await client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 401


class TestUpdatePreferences:
    @pytest.mark.anyio
    async def test_upsert_creates_new_row(self, client):
        """PUT /users/me/preferences → 200, creates row via upsert."""
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP_PREFS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP_PREFS}.update_user_preferences",
                    new_callable=AsyncMock,
                    return_value={
                        "theme": "dark",
                        "notify_mentions": True,
                        "notify_replies": True,
                        "notify_sig_posts": True,
                    },
                ),
            ):
                resp = await client.put(
                    "/api/v1/users/me/preferences",
                    json={"theme": "dark"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["theme"] == "dark"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upsert_updates_existing_row(self, client):
        """PUT /users/me/preferences → 200, updates existing row."""
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP_PREFS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP_PREFS}.update_user_preferences",
                    new_callable=AsyncMock,
                    return_value={
                        "theme": "dark",
                        "notify_mentions": False,
                        "notify_replies": True,
                        "notify_sig_posts": True,
                    },
                ),
            ):
                resp = await client.put(
                    "/api/v1/users/me/preferences",
                    json={"theme": "dark", "notify_mentions": False},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["theme"] == "dark"
                assert data["notify_mentions"] is False
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_invalid_theme_returns_422(self, client):
        """PUT /users/me/preferences with invalid theme → 422."""
        try:
            _override_auth("MEMBER")
            resp = await client.put(
                "/api/v1/users/me/preferences",
                json={"theme": "neon"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_partial_update_only_updates_provided_fields(self, client):
        """PUT /users/me/preferences with partial data only updates those fields."""
        try:
            payload, uid = _override_auth("MEMBER")
            mock_update = AsyncMock(
                return_value={
                    "theme": "light",
                    "notify_mentions": True,
                    "notify_replies": False,
                    "notify_sig_posts": True,
                }
            )
            with (
                patch(f"{_EP_PREFS}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP_PREFS}.update_user_preferences", mock_update),
            ):
                resp = await client.put(
                    "/api/v1/users/me/preferences",
                    json={"notify_replies": False},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["notify_replies"] is False
                # Verify only notify_replies was passed (theme excluded since None)
                call_args = mock_update.call_args
                data_arg = call_args[0][1]  # second positional arg is the data dict
                assert "theme" not in data_arg
                assert data_arg["notify_replies"] is False
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_unauthenticated_returns_401(self, client):
        """PUT /users/me/preferences without auth → 401."""
        resp = await client.put(
            "/api/v1/users/me/preferences",
            json={"theme": "dark"},
        )
        assert resp.status_code == 401


class TestUpdatePreferencesRateLimit:
    @pytest.mark.anyio
    async def test_update_preferences_rate_limited(self, client):
        """PUT /users/me/preferences → 429 when rate limited."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP_PREFS}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.put(
                    "/api/v1/users/me/preferences",
                    json={"theme": "dark"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestPreferencesRepo:
    """Unit tests for the preferences repository functions."""

    @pytest.mark.anyio
    async def test_get_preferences_returns_none_when_empty(self, mock_pool, mock_conn):
        """get_preferences returns None when no row exists."""
        mock_conn.fetchrow.return_value = None
        with patch("app.repositories.preferences_repo.get_pool", return_value=mock_pool):
            from app.repositories.preferences_repo import get_preferences

            result = await get_preferences(uuid.uuid4())
            assert result is None

    @pytest.mark.anyio
    async def test_get_preferences_returns_row(self, mock_pool, mock_conn):
        """get_preferences returns dict when row exists."""
        expected = {
            "theme": "dark",
            "notify_mentions": False,
            "notify_replies": True,
            "notify_sig_posts": True,
        }
        mock_conn.fetchrow.return_value = expected
        with patch("app.repositories.preferences_repo.get_pool", return_value=mock_pool):
            from app.repositories.preferences_repo import get_preferences

            result = await get_preferences(uuid.uuid4())
            assert result == expected

    @pytest.mark.anyio
    async def test_upsert_preferences(self, mock_pool, mock_conn):
        """upsert_preferences executes INSERT ON CONFLICT and returns row."""
        expected = {
            "theme": "dark",
            "notify_mentions": True,
            "notify_replies": True,
            "notify_sig_posts": True,
        }
        mock_conn.fetchrow.return_value = expected
        with patch("app.repositories.preferences_repo.get_pool", return_value=mock_pool):
            from app.repositories.preferences_repo import upsert_preferences

            result = await upsert_preferences(uuid.uuid4(), {"theme": "dark"})
            assert result == expected
            # Verify SQL was called
            mock_conn.fetchrow.assert_called_once()
            sql_arg = mock_conn.fetchrow.call_args[0][0]
            assert "INSERT INTO user_preferences" in sql_arg
            assert "ON CONFLICT" in sql_arg


class TestPreferencesService:
    """Unit tests for the preferences service functions."""

    @pytest.mark.anyio
    async def test_get_user_preferences_defaults(self):
        """get_user_preferences returns defaults when repo returns None."""
        with patch(
            "app.services.preferences.preferences_repo.get_preferences",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from app.services.preferences import get_user_preferences

            result = await get_user_preferences(uuid.uuid4())
            assert result["theme"] == "light"
            assert result["notify_mentions"] is True

    @pytest.mark.anyio
    async def test_get_user_preferences_saved(self):
        """get_user_preferences returns saved values when row exists."""
        saved = {
            "theme": "dark",
            "notify_mentions": False,
            "notify_replies": True,
            "notify_sig_posts": False,
        }
        with patch(
            "app.services.preferences.preferences_repo.get_preferences",
            new_callable=AsyncMock,
            return_value=saved,
        ):
            from app.services.preferences import get_user_preferences

            result = await get_user_preferences(uuid.uuid4())
            assert result == saved

    @pytest.mark.anyio
    async def test_update_user_preferences(self):
        """update_user_preferences calls repo upsert."""
        expected = {
            "theme": "dark",
            "notify_mentions": True,
            "notify_replies": True,
            "notify_sig_posts": True,
        }
        with patch(
            "app.services.preferences.preferences_repo.upsert_preferences",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            from app.services.preferences import update_user_preferences

            result = await update_user_preferences(uuid.uuid4(), {"theme": "dark"})
            assert result == expected
