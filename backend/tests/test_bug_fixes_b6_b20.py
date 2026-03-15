"""Tests for bug fixes B6, B7, B8, B11, B19, B20.

B7:  Invalid Content-Length returns 400
B8:  Event handlers re-raise for event bus retry
B11: Idempotency middleware graceful degradation when Redis unavailable
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

_TEST_CSRF = "csrf-test"


@pytest.fixture
async def client():
    from app.main import app

    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"csrf_token": _TEST_CSRF},
            headers={"X-CSRF-Token": _TEST_CSRF},
        ) as ac:
            yield ac


def _override_auth(role="MEMBER", user_id="00000000-0000-0000-0000-aaaaaaaaaaaa"):
    from app.core.deps import get_current_user
    from app.main import app

    payload = {"sub": user_id, "role": role, "jti": "jti-test"}
    app.dependency_overrides[get_current_user] = lambda: payload


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


# ── B7: Invalid Content-Length returns 400 ──────────────────────────────


class TestInvalidContentLength:
    """Non-numeric Content-Length header should return 400, not crash."""

    @pytest.mark.anyio
    async def test_invalid_content_length_returns_400(self, client: AsyncClient):
        """Malicious Content-Length: abc should return 400 Bad Request."""
        resp = await client.get(
            "/api/v1/health/live",
            headers={"Content-Length": "abc"},
        )
        assert resp.status_code == 400
        assert "Invalid Content-Length" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_negative_content_length_returns_400(self, client: AsyncClient):
        """Content-Length with non-numeric value returns 400."""
        resp = await client.get(
            "/api/v1/health/live",
            headers={"Content-Length": "not-a-number"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_valid_content_length_passes_through(self, client: AsyncClient):
        """A normal numeric Content-Length should not be rejected."""
        resp = await client.get(
            "/api/v1/health/live",
            headers={"Content-Length": "0"},
        )
        # Should pass through (not 400)
        assert resp.status_code != 400


# ── B8: Event handlers re-raise for retry ───────────────────────────────


class TestEventHandlerReRaise:
    """Event handlers should re-raise exceptions so the event bus can retry."""

    @pytest.mark.anyio
    async def test_on_post_deleted_reraises_for_retry(self):
        """_on_post_deleted should re-raise after logging so event bus retries."""
        from app.event_handlers import _on_post_deleted

        mock_create = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            with pytest.raises(RuntimeError, match="DB error"):
                await _on_post_deleted(
                    post_owner_id=str(uuid.uuid4()),
                    admin_user_id=str(uuid.uuid4()),
                    post_id=str(uuid.uuid4()),
                )

    @pytest.mark.anyio
    async def test_on_application_reviewed_reraises_for_retry(self):
        """_on_application_reviewed should re-raise after logging."""
        from app.event_handlers import _on_application_reviewed

        mock_create = AsyncMock(side_effect=ConnectionError("timeout"))
        mock_check = AsyncMock(return_value=True)

        with (
            patch("app.services.notification.create_notification", mock_create),
            patch("app.event_handlers._check_idempotent", mock_check),
        ):
            with pytest.raises(ConnectionError, match="timeout"):
                await _on_application_reviewed(
                    applicant_uid=str(uuid.uuid4()),
                    reviewer_uid=str(uuid.uuid4()),
                    action="APPROVED",
                )

    @pytest.mark.anyio
    async def test_on_user_banned_reraises_for_retry(self):
        """_on_user_banned should re-raise after logging."""
        from app.event_handlers import _on_user_banned

        mock_logout = AsyncMock(side_effect=RuntimeError("WS error"))

        with patch("app.api.v1.endpoints.ws.force_logout", mock_logout):
            with pytest.raises(RuntimeError, match="WS error"):
                await _on_user_banned(user_id=str(uuid.uuid4()))

    @pytest.mark.anyio
    async def test_on_notification_created_reraises_for_retry(self):
        """_on_notification_created should re-raise after logging."""
        from app.event_handlers import _on_notification_created

        mock_send = AsyncMock(side_effect=RuntimeError("WS unavailable"))

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            with pytest.raises(RuntimeError, match="WS unavailable"):
                await _on_notification_created(
                    user_id=str(uuid.uuid4()),
                    notification={"type": "test"},
                )

    @pytest.mark.anyio
    async def test_on_user_role_changed_reraises_for_retry(self):
        """_on_user_role_changed should re-raise after logging."""
        from app.event_handlers import _on_user_role_changed

        mock_send = AsyncMock(side_effect=RuntimeError("WS down"))

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            with pytest.raises(RuntimeError, match="WS down"):
                await _on_user_role_changed(
                    user_id=str(uuid.uuid4()),
                    new_role="ADMIN",
                )

    @pytest.mark.anyio
    async def test_event_bus_retries_on_handler_exception(self):
        """Verify the event bus actually retries when handler raises."""
        from app.core.event_bus import clear, emit, on

        call_count = 0

        async def flaky_handler(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient failure")

        clear()
        on("test.retry", flaky_handler)

        result = await emit("test.retry")
        # Should have retried (1 initial + 2 retries = 3 calls)
        assert call_count == 3
        assert result.ok  # Succeeded on third attempt

        clear()


# ── B11: Idempotency Redis unavailable ──────────────────────────────────


class TestIdempotencyRedisUnavailable:
    """When Redis is down, idempotency middleware should gracefully degrade."""

    @pytest.mark.anyio
    async def test_idempotency_redis_unavailable_graceful(self, client: AsyncClient):
        """Request proceeds normally when Redis is unavailable for idempotency."""
        _override_auth("MEMBER")
        try:
            with (
                patch(
                    "app.middleware.idempotency.get_redis",
                    side_effect=ConnectionError("Redis down"),
                ),
                patch(
                    "app.api.v1.endpoints.posts.create_post",
                    new_callable=AsyncMock,
                    return_value={
                        "id": "ok-post-id",
                        "title": "Test",
                        "content": "<p>Hello</p>",
                        "author": {
                            "id": "uid",
                            "username": "u",
                            "display_name": "u",
                            "avatar_url": None,
                        },
                        "sig": None,
                        "category": None,
                        "keywords": [],
                        "comment_count": 0,
                        "view_count": 0,
                        "is_pinned": False,
                        "is_deleted": False,
                        "allow_comments": True,
                        "reactions": {},
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                        "version": 1,
                    },
                ),
                patch(
                    "app.api.v1.endpoints.posts.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.post(
                    "/api/v1/posts",
                    json={
                        "title": "Test",
                        "content": "<p>Hello</p>",
                        "allow_comments": True,
                    },
                    headers={
                        "Idempotency-Key": "redis-down-key",
                        "Authorization": "Bearer faketoken123",
                    },
                )
            # Request should succeed even though Redis is unavailable
            assert resp.status_code == 201
            assert resp.json()["id"] == "ok-post-id"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_idempotency_redis_get_raises_graceful(self, client: AsyncClient):
        """When redis.get() raises, request proceeds without idempotency."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis get failed"))

        _override_auth("MEMBER")
        try:
            with (
                patch(
                    "app.middleware.idempotency.get_redis",
                    return_value=mock_redis,
                ),
                patch(
                    "app.api.v1.endpoints.posts.create_post",
                    new_callable=AsyncMock,
                    return_value={
                        "id": "fallback-id",
                        "title": "T",
                        "content": "<p>Hi</p>",
                        "author": {
                            "id": "uid",
                            "username": "u",
                            "display_name": "u",
                            "avatar_url": None,
                        },
                        "sig": None,
                        "category": None,
                        "keywords": [],
                        "comment_count": 0,
                        "view_count": 0,
                        "is_pinned": False,
                        "is_deleted": False,
                        "allow_comments": True,
                        "reactions": {},
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                        "version": 1,
                    },
                ),
                patch(
                    "app.api.v1.endpoints.posts.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.post(
                    "/api/v1/posts",
                    json={
                        "title": "T",
                        "content": "<p>Hi</p>",
                        "allow_comments": True,
                    },
                    headers={
                        "Idempotency-Key": "redis-get-fail-key",
                        "Authorization": "Bearer faketoken123",
                    },
                )
            assert resp.status_code == 201
            assert resp.json()["id"] == "fallback-id"
        finally:
            _clear_overrides()
