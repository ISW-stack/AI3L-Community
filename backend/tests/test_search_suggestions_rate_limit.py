"""Tests for Bug #9: Search suggestions endpoint must have rate limiting."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.posts"


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


class TestSearchSuggestionsRateLimit:
    """Verify rate limiting on GET /posts/suggestions."""

    @pytest.mark.anyio
    async def test_suggestions_within_rate_limit(self, client):
        """Normal request within rate limit should succeed."""
        payload, uid = _override_auth("MEMBER")
        try:
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    "app.repositories.post_repo.get_search_suggestions",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
                patch(
                    "app.repositories.post_repo.get_keyword_suggestions",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
            ):
                resp = await client.get("/api/v1/posts/suggestions?q=test")
                assert resp.status_code == 200
                data = resp.json()
                assert data["posts"] == []
                assert data["keywords"] == []
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_suggestions_rate_limit_exceeded(self, client):
        """Request exceeding rate limit should return 429."""
        payload, uid = _override_auth("MEMBER")
        try:
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.get("/api/v1/posts/suggestions?q=test")
                assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_suggestions_rate_limit_key_uses_user_id(self, client):
        """Rate limit key should include user sub for per-user limiting."""
        user_id = str(uuid.uuid4())
        payload, uid = _override_auth("MEMBER", user_id=user_id)
        try:
            with (
                patch(
                    f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True
                ) as mock_rl,
                patch(
                    "app.repositories.post_repo.get_search_suggestions",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
                patch(
                    "app.repositories.post_repo.get_keyword_suggestions",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
            ):
                await client.get("/api/v1/posts/suggestions?q=test")
                mock_rl.assert_awaited_once()
                call_args = mock_rl.call_args[0]
                assert call_args[0] == f"rl:suggestions:{user_id}"

        finally:
            _clear_overrides()


class TestSearchSuggestionsConstant:
    """Verify the rate limit constant exists."""

    def test_constant_exists(self):
        from app.core.constants import RATE_LIMIT_SEARCH_SUGGESTIONS

        assert isinstance(RATE_LIMIT_SEARCH_SUGGESTIONS, tuple)
        assert len(RATE_LIMIT_SEARCH_SUGGESTIONS) == 2
        max_count, window = RATE_LIMIT_SEARCH_SUGGESTIONS
        assert max_count == 30
        assert window == 60
