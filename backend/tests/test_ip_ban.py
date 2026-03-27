"""Tests for IP ban service, endpoints, and middleware."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ADMIN_EP = "app.api.v1.endpoints.admin"
_SVC = "app.services.ip_ban"


def _override_auth(role="SUPER_ADMIN", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


def _make_ban_dict(
    ban_id=None,
    ip="192.168.1.100",
    reason="spam",
    banned_by=None,
    expires_at=None,
):
    now = datetime.now(timezone.utc)
    return {
        "id": ban_id or uuid.uuid4(),
        "ip_address": ip,
        "reason": reason,
        "banned_by": banned_by or uuid.uuid4(),
        "expires_at": expires_at,
        "created_at": now,
    }


# ═══════════════════════════════════════════════════════════════
#  IP Ban Service Tests
# ═══════════════════════════════════════════════════════════════


class TestIsIpBanned:
    @pytest.mark.anyio
    async def test_is_ip_banned_cached_true(self):
        """Redis returns '1' -> True without hitting DB."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="1")

        with (
            patch(f"{_SVC}.get_redis", return_value=mock_redis),
            patch(f"{_SVC}.ip_ban_repo") as mock_repo,
        ):
            from app.services.ip_ban import is_ip_banned

            result = await is_ip_banned("10.0.0.1")
            assert result is True
            mock_repo.find_by_ip.assert_not_called()

    @pytest.mark.anyio
    async def test_is_ip_banned_cached_false(self):
        """Redis returns '0' -> False without hitting DB."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="0")

        with (
            patch(f"{_SVC}.get_redis", return_value=mock_redis),
            patch(f"{_SVC}.ip_ban_repo") as mock_repo,
        ):
            from app.services.ip_ban import is_ip_banned

            result = await is_ip_banned("10.0.0.1")
            assert result is False
            mock_repo.find_by_ip.assert_not_called()

    @pytest.mark.anyio
    async def test_is_ip_banned_cache_miss_banned(self):
        """Redis returns None, DB returns a ban -> cache '1', return True."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        ban = _make_ban_dict(ip="10.0.0.1")

        with (
            patch(f"{_SVC}.get_redis", return_value=mock_redis),
            patch(f"{_SVC}.ip_ban_repo") as mock_repo,
        ):
            mock_repo.find_by_ip = AsyncMock(return_value=ban)

            from app.services.ip_ban import is_ip_banned

            result = await is_ip_banned("10.0.0.1")
            assert result is True
            mock_redis.set.assert_called_once_with("ip_ban:10.0.0.1", "1", ex=300)

    @pytest.mark.anyio
    async def test_is_ip_banned_cache_miss_not_banned(self):
        """Redis returns None, DB returns None -> cache '0', return False."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with (
            patch(f"{_SVC}.get_redis", return_value=mock_redis),
            patch(f"{_SVC}.ip_ban_repo") as mock_repo,
        ):
            mock_repo.find_by_ip = AsyncMock(return_value=None)

            from app.services.ip_ban import is_ip_banned

            result = await is_ip_banned("10.0.0.1")
            assert result is False
            mock_redis.set.assert_called_once_with("ip_ban:10.0.0.1", "0", ex=300)


class TestBanIpService:
    @pytest.mark.anyio
    async def test_ban_ip_creates_and_invalidates_cache(self):
        """ban_ip creates DB record and deletes Redis cache key."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        ban = _make_ban_dict(ip="10.0.0.5")
        banned_by = uuid.uuid4()

        with (
            patch(f"{_SVC}.get_redis", return_value=mock_redis),
            patch(f"{_SVC}.ip_ban_repo") as mock_repo,
        ):
            mock_repo.create = AsyncMock(return_value=ban)

            from app.services.ip_ban import ban_ip

            result = await ban_ip(ip="10.0.0.5", reason="spam", banned_by=banned_by)
            assert result["ip_address"] == "10.0.0.5"
            mock_repo.create.assert_called_once()
            mock_redis.set.assert_called_once_with("ip_ban:10.0.0.5", "1", ex=300)


class TestUnbanIpService:
    @pytest.mark.anyio
    async def test_unban_ip_deletes_and_invalidates_cache(self):
        """unban_ip deletes DB record and clears cache."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        ban_id = uuid.uuid4()

        # Mock the pool for the inline query in unban_ip
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"ip_address": "10.0.0.5"})
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_redis", return_value=mock_redis),
            patch(f"{_SVC}.ip_ban_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            mock_repo.delete = AsyncMock(return_value=True)

            from app.services.ip_ban import unban_ip

            result = await unban_ip(ban_id)
            assert result is True
            mock_conn.fetchrow.assert_called_once()
            mock_redis.set.assert_called_once_with("ip_ban:10.0.0.5", "0", ex=300)

    @pytest.mark.anyio
    async def test_unban_ip_not_found(self):
        """unban_ip returns False when ban doesn't exist."""
        ban_id = uuid.uuid4()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch(f"{_SVC}.get_redis", return_value=AsyncMock()),
            patch(f"{_SVC}.ip_ban_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            mock_repo.delete = AsyncMock(return_value=False)

            from app.services.ip_ban import unban_ip

            result = await unban_ip(ban_id)
            assert result is False


# ═══════════════════════════════════════════════════════════════
#  IP Ban Endpoint Tests
# ═══════════════════════════════════════════════════════════════


class TestListIpBansEndpoint:
    @pytest.mark.anyio
    async def test_list_ip_bans(self, client):
        """GET /admin/ip-bans -> 200 with paginated list."""
        ban = _make_ban_dict()
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_SVC}.list_ip_bans",
                new_callable=AsyncMock,
                return_value=([ban], 1),
            ):
                resp = await client.get(
                    "/api/v1/admin/ip-bans",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["bans"]) == 1
                assert data["bans"][0]["ip_address"] == "192.168.1.100"
        finally:
            _clear_overrides()


class TestBanIpEndpoint:
    @pytest.mark.anyio
    async def test_ban_ip_endpoint_success(self, client):
        """POST /admin/ip-bans with valid IP -> 201."""
        ban = _make_ban_dict(ip="10.0.0.99")
        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    f"{_SVC}.ban_ip",
                    new_callable=AsyncMock,
                    return_value=ban,
                ),
                patch("app.core.event_bus.emit", new_callable=AsyncMock),
            ):
                resp = await client.post(
                    "/api/v1/admin/ip-bans",
                    json={"ip_address": "10.0.0.99", "reason": "spam"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["ip_address"] == "10.0.0.99"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_ban_ip_invalid_format(self, client):
        """POST /admin/ip-bans with invalid IP -> 422."""
        try:
            _override_auth("SUPER_ADMIN")
            resp = await client.post(
                "/api/v1/admin/ip-bans",
                json={"ip_address": "not-an-ip", "reason": "test"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


class TestUnbanIpEndpoint:
    @pytest.mark.anyio
    async def test_unban_ip_endpoint_success(self, client):
        """DELETE /admin/ip-bans/{id} -> 200."""
        ban_id = uuid.uuid4()
        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    f"{_SVC}.unban_ip",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch("app.core.event_bus.emit", new_callable=AsyncMock),
            ):
                resp = await client.delete(
                    f"/api/v1/admin/ip-bans/{ban_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "removed" in resp.json()["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_unban_ip_not_found(self, client):
        """DELETE /admin/ip-bans/{id} with non-existent ID -> 404."""
        ban_id = uuid.uuid4()
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_SVC}.unban_ip",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.delete(
                    f"/api/v1/admin/ip-bans/{ban_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()


class TestIpBanEndpointsForbidden:
    @pytest.mark.anyio
    async def test_ip_ban_endpoints_forbidden_for_admin(self, client):
        """ADMIN role gets 403 on all ip-ban endpoints."""
        try:
            _override_auth("ADMIN")

            resp_list = await client.get(
                "/api/v1/admin/ip-bans",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp_list.status_code == 403

            resp_ban = await client.post(
                "/api/v1/admin/ip-bans",
                json={"ip_address": "10.0.0.1", "reason": "test"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp_ban.status_code == 403

            resp_unban = await client.delete(
                f"/api/v1/admin/ip-bans/{uuid.uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp_unban.status_code == 403
        finally:
            _clear_overrides()


# ═══════════════════════════════════════════════════════════════
#  IP Ban Middleware Tests
# ═══════════════════════════════════════════════════════════════


class TestIpBanMiddleware:
    @pytest.mark.anyio
    async def test_middleware_blocks_banned_ip(self, client):
        """Request from a banned IP -> 403."""
        with patch(
            f"{_SVC}.is_ip_banned",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await client.get("/api/v1/admin/dashboard")
            assert resp.status_code == 403
            assert "banned" in resp.json()["detail"].lower()

    @pytest.mark.anyio
    async def test_middleware_allows_clean_ip(self, unauthed_client):
        """Request from a clean IP passes through (not blocked by middleware)."""
        with patch(
            f"{_SVC}.is_ip_banned",
            new_callable=AsyncMock,
            return_value=False,
        ):
            # The request will pass the middleware but may fail for other reasons
            # (e.g., auth). We just check it's NOT 403 with "banned" message.
            resp = await unauthed_client.get("/api/v1/admin/dashboard")
            # Should not be the IP ban 403
            if resp.status_code == 403:
                assert "banned" not in resp.json().get("detail", "").lower()
