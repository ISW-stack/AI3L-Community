"""Tests for Bug #13: CommentListResponse must include page and total_pages."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.comments"


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


def _make_comment(post_id=None, user_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(uuid.uuid4()),
        "post_id": str(post_id or uuid.uuid4()),
        "content": "Test comment",
        "author": {
            "id": uid,
            "username": "testuser",
            "display_name": "Test User",
            "avatar_url": None,
        },
        "parent_id": None,
        "mentions": None,
        "reactions": {},
        "created_at": now,
        "updated_at": now,
    }


class TestCommentPaginationFields:
    """Verify CommentListResponse includes page and total_pages."""

    @pytest.mark.anyio
    async def test_response_includes_pagination_fields(self, client):
        """GET /posts/{pid}/comments → response includes page and total_pages."""
        post_id = uuid.uuid4()
        comment = _make_comment(post_id=post_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value={"id": post_id}
                ),
                patch(f"{_EP}.list_comments", new_callable=AsyncMock, return_value=([comment], 1)),
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/comments",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert "page" in data
                assert "total_pages" in data
                assert data["page"] == 1
                assert data["total_pages"] == 1
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_pagination_page_2(self, client):
        """GET /posts/{pid}/comments?page=2&page_size=10 → page=2."""
        post_id = uuid.uuid4()
        comment = _make_comment(post_id=post_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value={"id": post_id}
                ),
                patch(f"{_EP}.list_comments", new_callable=AsyncMock, return_value=([comment], 25)),
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/comments?page=2&page_size=10",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["page"] == 2
                assert data["total_pages"] == 3  # ceil(25/10) = 3
                assert data["total"] == 25
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_pagination_total_pages_calculation(self, client):
        """Verify total_pages = max(1, ceil(total / page_size))."""
        post_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value={"id": post_id}
                ),
                patch(f"{_EP}.list_comments", new_callable=AsyncMock, return_value=([], 0)),
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/comments?page=1&page_size=50",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                # Even with 0 results, total_pages should be 1 (minimum)
                assert data["total_pages"] == 1
                assert data["page"] == 1
                assert data["total"] == 0
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_pagination_exact_page_boundary(self, client):
        """When total is exact multiple of page_size, total_pages = total / page_size."""
        post_id = uuid.uuid4()
        comments = [_make_comment(post_id=post_id) for _ in range(10)]

        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value={"id": post_id}
                ),
                patch(f"{_EP}.list_comments", new_callable=AsyncMock, return_value=(comments, 20)),
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/comments?page=1&page_size=10",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total_pages"] == 2  # 20 / 10 = 2
                assert data["page"] == 1
        finally:
            _clear_overrides()


class TestCommentListResponseSchema:
    """Verify the schema itself has the new fields."""

    def test_schema_has_pagination_fields(self):
        """CommentListResponse schema includes page and total_pages."""
        from app.schemas.comment import CommentListResponse

        fields = CommentListResponse.model_fields
        assert "page" in fields
        assert "total_pages" in fields

    def test_schema_defaults(self):
        """CommentListResponse defaults: page=1, total_pages=1."""
        from app.schemas.comment import CommentListResponse

        resp = CommentListResponse(comments=[], total=0)
        assert resp.page == 1
        assert resp.total_pages == 1

    def test_schema_with_explicit_values(self):
        """CommentListResponse accepts explicit page and total_pages."""
        from app.schemas.comment import CommentListResponse

        resp = CommentListResponse(comments=[], total=50, page=3, total_pages=5)
        assert resp.page == 3
        assert resp.total_pages == 5
