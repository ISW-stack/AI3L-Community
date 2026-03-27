"""Tests for search suggestions endpoint — GET /posts/suggestions."""

import uuid
from unittest.mock import ANY, AsyncMock, patch

import pytest

_REPO = "app.repositories.post_repo"


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


_RATE_LIMIT = "app.api.v1.endpoints.posts.check_rate_limit"


class TestSearchSuggestions:
    @pytest.mark.anyio
    async def test_returns_empty_results(self, client):
        """GET /posts/suggestions?q=xyz → 200 with empty posts and keywords."""
        try:
            _override_auth("MEMBER")
            with (
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_REPO}.get_search_suggestions",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
                patch(
                    f"{_REPO}.get_keyword_suggestions",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
            ):
                resp = await client.get(
                    "/api/v1/posts/suggestions?q=xyz",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["posts"] == []
                assert data["keywords"] == []
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_returns_matching_posts(self, client):
        """GET /posts/suggestions?q=machine → 200 with matching posts."""
        post_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER")
            with (
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_REPO}.get_search_suggestions",
                    new_callable=AsyncMock,
                    return_value=[{"id": uuid.UUID(post_id), "title": "Machine Learning 101"}],
                ),
                patch(
                    f"{_REPO}.get_keyword_suggestions",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
            ):
                resp = await client.get(
                    "/api/v1/posts/suggestions?q=machine",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["posts"]) == 1
                assert data["posts"][0]["title"] == "Machine Learning 101"
                assert data["posts"][0]["id"] == post_id
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_returns_matching_keywords(self, client):
        """GET /posts/suggestions?q=ai → 200 with matching keywords."""
        try:
            _override_auth("MEMBER")
            with (
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_REPO}.get_search_suggestions",
                    new_callable=AsyncMock,
                    return_value=[],
                ),
                patch(
                    f"{_REPO}.get_keyword_suggestions",
                    new_callable=AsyncMock,
                    return_value=["AI ethics", "AI literacy"],
                ),
            ):
                resp = await client.get(
                    "/api/v1/posts/suggestions?q=ai",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["keywords"] == ["AI ethics", "AI literacy"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_respects_limit_parameter(self, client):
        """GET /posts/suggestions?q=test&limit=2 → passes limit to repo."""
        try:
            _override_auth("MEMBER")
            mock_posts = AsyncMock(return_value=[])
            mock_kw = AsyncMock(return_value=[])
            with (
                patch(_RATE_LIMIT, new_callable=AsyncMock, return_value=True),
                patch(f"{_REPO}.get_search_suggestions", mock_posts),
                patch(f"{_REPO}.get_keyword_suggestions", mock_kw),
            ):
                resp = await client.get(
                    "/api/v1/posts/suggestions?q=test&limit=2",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                # Verify limit and viewer_id were passed through
                mock_posts.assert_called_once_with("test", limit=2, viewer_id=ANY)
                mock_kw.assert_called_once_with("test", limit=2, viewer_id=ANY)
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_query_too_short_returns_422(self, client):
        """GET /posts/suggestions?q=a → 422 (min_length=2)."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/posts/suggestions?q=a",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_unauthenticated_returns_401(self, unauthed_client):
        """GET /posts/suggestions?q=test without auth → 401."""
        resp = await unauthed_client.get("/api/v1/posts/suggestions?q=test")
        assert resp.status_code == 401


class TestSearchSuggestionsRepo:
    """Unit tests for the search suggestion repo functions."""

    @pytest.mark.anyio
    async def test_get_search_suggestions(self, mock_pool, mock_conn):
        """get_search_suggestions executes ILIKE query and returns dicts."""
        post_id = uuid.uuid4()
        mock_conn.fetch.return_value = [{"id": post_id, "title": "AI Research"}]
        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_search_suggestions

            result = await get_search_suggestions("ai", limit=5)
            assert len(result) == 1
            assert result[0]["title"] == "AI Research"
            # Verify SQL contains ILIKE
            sql_arg = mock_conn.fetch.call_args[0][0]
            assert "ILIKE" in sql_arg

    @pytest.mark.anyio
    async def test_get_keyword_suggestions(self, mock_pool, mock_conn):
        """get_keyword_suggestions returns list of keyword strings."""
        mock_conn.fetch.return_value = [{"kw": "AI ethics"}, {"kw": "AI literacy"}]
        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_keyword_suggestions

            result = await get_keyword_suggestions("ai", limit=5)
            assert result == ["AI ethics", "AI literacy"]

    @pytest.mark.anyio
    async def test_get_search_suggestions_empty(self, mock_pool, mock_conn):
        """get_search_suggestions returns empty list when no matches."""
        mock_conn.fetch.return_value = []
        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_search_suggestions

            result = await get_search_suggestions("zzzzz", limit=5)
            assert result == []

    @pytest.mark.anyio
    async def test_get_keyword_suggestions_empty(self, mock_pool, mock_conn):
        """get_keyword_suggestions returns empty list when no matches."""
        mock_conn.fetch.return_value = []
        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import get_keyword_suggestions

            result = await get_keyword_suggestions("zzzzz", limit=5)
            assert result == []
