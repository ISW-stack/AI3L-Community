"""Tests for Q&A sort options, type filtering, and trending endpoint."""

import uuid
from datetime import datetime, timezone
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


def _make_post(post_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(post_id or uuid.uuid4()),
        "title": "Test Post",
        "content": "<p>Body</p>",
        "author": {
            "id": uid,
            "username": "testuser",
            "display_name": "Test User",
            "avatar_url": None,
        },
        "category_id": None,
        "category_name": None,
        "keywords": ["test"],
        "allow_comments": True,
        "version": 1,
        "comment_count": 0,
        "created_at": now,
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# 1. Sort regex validation
# ---------------------------------------------------------------------------


class TestSortRegexValidation:
    @pytest.mark.anyio
    async def test_sort_most_answers_accepted(self, client):
        """GET /posts?sort=most_answers → 200."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={
                    "posts": [],
                    "total": 0,
                    "total_pages": 1,
                    "next_cursor": None,
                    "has_more": False,
                },
            ):
                resp = await client.get(
                    "/api/v1/posts?sort=most_answers",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sort_unanswered_accepted(self, client):
        """GET /posts?sort=unanswered → 200."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={
                    "posts": [],
                    "total": 0,
                    "total_pages": 1,
                    "next_cursor": None,
                    "has_more": False,
                },
            ):
                resp = await client.get(
                    "/api/v1/posts?sort=unanswered",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_sort_invalid_rejected(self, client):
        """GET /posts?sort=invalid_sort → 422."""
        try:
            _override_auth("MEMBER")
            resp = await client.get(
                "/api/v1/posts?sort=invalid_sort",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 2. Search with type filter
# ---------------------------------------------------------------------------


class TestSearchTypeFilter:
    @pytest.mark.anyio
    async def test_search_with_type_question(self, client):
        """POST /posts/search with type=question passes post_type to service."""
        post = _make_post()

        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.search_posts",
                new_callable=AsyncMock,
                return_value=([post], 1, 1),
            ) as mock_search:
                resp = await client.post(
                    "/api/v1/posts/search",
                    json={"keyword": "test", "type": "question"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_search.call_args.kwargs
                assert call_kwargs.get("post_type") == "question"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_search_with_sort_most_answers(self, client):
        """POST /posts/search with sort=most_answers → 200."""
        post = _make_post()

        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.search_posts",
                new_callable=AsyncMock,
                return_value=([post], 1, 1),
            ) as mock_search:
                resp = await client.post(
                    "/api/v1/posts/search",
                    json={"sort": "most_answers"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_search.call_args.kwargs
                assert call_kwargs.get("sort") == "most_answers"
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 3. Trending with type filter
# ---------------------------------------------------------------------------


class TestTrendingTypeFilter:
    @pytest.mark.anyio
    async def test_trending_with_type_question(self, client):
        """GET /posts/trending?type=question passes post_type to service."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.get_trending_posts",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_trending:
                resp = await client.get(
                    "/api/v1/posts/trending?type=question",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_trending.call_args.kwargs
                assert call_kwargs.get("post_type") == "question"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_trending_without_type_backward_compat(self, client):
        """GET /posts/trending without type → 200 (backward compat)."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.get_trending_posts",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_trending:
                resp = await client.get(
                    "/api/v1/posts/trending",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_trending.call_args.kwargs
                assert call_kwargs.get("post_type") is None
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# 4. List with new sorts + type filter
# ---------------------------------------------------------------------------


class TestListNewSorts:
    @pytest.mark.anyio
    async def test_list_most_answers_with_type(self, client):
        """GET /posts?sort=most_answers&type=question passes both params."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={
                    "posts": [],
                    "total": 0,
                    "total_pages": 1,
                    "next_cursor": None,
                    "has_more": False,
                },
            ) as mock_list:
                resp = await client.get(
                    "/api/v1/posts?sort=most_answers&type=question",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_list.call_args.kwargs
                assert call_kwargs.get("sort") == "most_answers"
                assert call_kwargs.get("post_type") == "question"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_unanswered_with_type(self, client):
        """GET /posts?sort=unanswered&type=question passes both params."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={
                    "posts": [],
                    "total": 0,
                    "total_pages": 1,
                    "next_cursor": None,
                    "has_more": False,
                },
            ) as mock_list:
                resp = await client.get(
                    "/api/v1/posts?sort=unanswered&type=question",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                call_kwargs = mock_list.call_args.kwargs
                assert call_kwargs.get("sort") == "unanswered"
                assert call_kwargs.get("post_type") == "question"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_list_passes_sort_and_post_type_to_service(self, client):
        """Verify sort and post_type are forwarded to list_posts() service."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.list_posts",
                new_callable=AsyncMock,
                return_value={
                    "posts": [],
                    "total": 0,
                    "total_pages": 1,
                    "next_cursor": None,
                    "has_more": False,
                },
            ) as mock_list:
                resp = await client.get(
                    "/api/v1/posts?sort=popular&type=post",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_list.assert_called_once()
                call_kwargs = mock_list.call_args.kwargs
                assert "sort" in call_kwargs
                assert call_kwargs["sort"] == "popular"
                assert "post_type" in call_kwargs
                assert call_kwargs["post_type"] == "post"
        finally:
            _clear_overrides()
