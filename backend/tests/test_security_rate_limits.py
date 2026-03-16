"""Tests for rate limiting on heartbeat, ws-ticket, public stats, and forms list endpoints.

S09: /auth/heartbeat — 20 req/60s per user
S10: /auth/ws-ticket — 10 req/60s per user
S11: /public/stats — 30 req/60s per IP
S17: GET /forms — 30 req/60s per IP
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

_AUTH_EP = "app.api.v1.endpoints.auth"
_PUBLIC_EP = "app.api.v1.endpoints.public"
_FORMS_EP = "app.api.v1.endpoints.forms"


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": uid,
        "role": role,
        "jti": "jti-rl-test",
    }


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestHeartbeatRateLimit:
    """S09: /auth/heartbeat rate limited at 20 req/60s."""

    @pytest.mark.anyio
    async def test_heartbeat_rate_limited(self, client: AsyncClient):
        """When rate limit is exceeded, heartbeat returns 429."""
        _override_auth("MEMBER")
        try:
            with patch(
                f"{_AUTH_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.post("/api/v1/auth/heartbeat")
            assert resp.status_code == 429
            assert resp.json()["detail"]["code"] == "SYS_429"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_heartbeat_passes_when_under_limit(self, client: AsyncClient):
        """When rate limit is not exceeded, heartbeat succeeds."""
        _override_auth("MEMBER")
        try:
            with (
                patch(
                    f"{_AUTH_EP}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_AUTH_EP}.refresh_session_ttl",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.post("/api/v1/auth/heartbeat")
            assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_heartbeat_rate_limit_key_uses_user_id(self, client: AsyncClient):
        """Rate limit key includes the user ID."""
        uid = str(uuid.uuid4())
        _override_auth("MEMBER", user_id=uid)
        try:
            mock_rl = AsyncMock(return_value=False)
            with patch(f"{_AUTH_EP}.check_rate_limit", mock_rl):
                await client.post("/api/v1/auth/heartbeat")
            mock_rl.assert_called_once_with(f"rl:heartbeat:{uid}", 20, 60)
        finally:
            _clear_overrides()


class TestWsTicketRateLimit:
    """S10: /auth/ws-ticket rate limited at 10 req/60s."""

    @pytest.mark.anyio
    async def test_ws_ticket_rate_limited(self, client: AsyncClient):
        """When rate limit is exceeded, ws-ticket returns 429."""
        _override_auth("MEMBER")
        try:
            with patch(
                f"{_AUTH_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=False,
            ):
                resp = await client.post("/api/v1/auth/ws-ticket")
            assert resp.status_code == 429
            assert resp.json()["detail"]["code"] == "SYS_429"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_ws_ticket_passes_when_under_limit(self, client: AsyncClient):
        """When rate limit is not exceeded, ws-ticket succeeds."""
        _override_auth("MEMBER")
        try:
            with (
                patch(
                    f"{_AUTH_EP}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    f"{_AUTH_EP}.create_ws_ticket",
                    new_callable=AsyncMock,
                    return_value="ticket-abc",
                ),
            ):
                resp = await client.post("/api/v1/auth/ws-ticket")
            assert resp.status_code == 200
            assert resp.json()["ticket"] == "ticket-abc"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_ws_ticket_rate_limit_key_uses_user_id(self, client: AsyncClient):
        """Rate limit key includes the user ID."""
        uid = str(uuid.uuid4())
        _override_auth("MEMBER", user_id=uid)
        try:
            mock_rl = AsyncMock(return_value=False)
            with patch(f"{_AUTH_EP}.check_rate_limit", mock_rl):
                await client.post("/api/v1/auth/ws-ticket")
            mock_rl.assert_called_once_with(f"rl:ws_ticket:{uid}", 10, 60)
        finally:
            _clear_overrides()


class TestPublicStatsRateLimit:
    """S11: /public/stats rate limited at 30 req/60s per IP."""

    @pytest.mark.anyio
    async def test_public_stats_rate_limited(self, client: AsyncClient):
        """When rate limit is exceeded, public stats returns 429."""
        with patch(
            f"{_PUBLIC_EP}.check_rate_limit",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = await client.get("/api/v1/public/stats")
        assert resp.status_code == 429
        assert resp.json()["detail"]["code"] == "SYS_429"

    @pytest.mark.anyio
    async def test_public_stats_passes_when_under_limit(self, client: AsyncClient):
        """When rate limit is not exceeded, public stats succeeds."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        with (
            patch(
                f"{_PUBLIC_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                f"{_PUBLIC_EP}.dashboard_repo.count_users",
                new_callable=AsyncMock,
                return_value=100,
            ),
            patch(
                f"{_PUBLIC_EP}.dashboard_repo.count_posts",
                new_callable=AsyncMock,
                return_value=50,
            ),
            patch(
                f"{_PUBLIC_EP}.dashboard_repo.count_sigs",
                new_callable=AsyncMock,
                return_value=10,
            ),
            patch(f"{_PUBLIC_EP}.get_redis", return_value=mock_redis),
        ):
            resp = await client.get("/api/v1/public/stats")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_public_stats_rate_limit_uses_ip(self, client: AsyncClient):
        """Rate limit key includes the client IP."""
        mock_rl = AsyncMock(return_value=False)
        with patch(f"{_PUBLIC_EP}.check_rate_limit", mock_rl):
            await client.get("/api/v1/public/stats")
        # httpx test client reports IP as "testclient" or similar
        args = mock_rl.call_args[0]
        assert args[0].startswith("rl:public_stats:")
        assert args[1] == 30
        assert args[2] == 60


class TestFormsListRateLimit:
    """S17: GET /forms rate limited at 30 req/60s per IP."""

    @pytest.mark.anyio
    async def test_forms_list_rate_limited(self, client: AsyncClient):
        """When rate limit is exceeded, forms list returns 429."""
        with patch(
            f"{_FORMS_EP}.check_rate_limit",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = await client.get("/api/v1/forms")
        assert resp.status_code == 429
        assert resp.json()["detail"]["code"] == "SYS_429"

    @pytest.mark.anyio
    async def test_forms_list_passes_when_under_limit(self, client: AsyncClient):
        """When rate limit is not exceeded, forms list succeeds."""
        with (
            patch(
                f"{_FORMS_EP}.check_rate_limit",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                f"{_FORMS_EP}.list_standalone_forms_svc",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
        ):
            resp = await client.get("/api/v1/forms")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_forms_list_rate_limit_uses_ip(self, client: AsyncClient):
        """Rate limit key includes the client IP."""
        mock_rl = AsyncMock(return_value=False)
        with patch(f"{_FORMS_EP}.check_rate_limit", mock_rl):
            await client.get("/api/v1/forms")
        args = mock_rl.call_args[0]
        assert args[0].startswith("rl:forms_list:")
        assert args[1] == 30
        assert args[2] == 60
