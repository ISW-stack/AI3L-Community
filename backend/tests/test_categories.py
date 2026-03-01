"""Tests for categories endpoints — list, create."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_REPO = "app.repositories.category_repo"


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


class TestListCategories:
    @pytest.mark.anyio
    async def test_list_categories(self, client, mock_pool, mock_conn):
        """GET /categories → 200."""
        cat_id = uuid.uuid4()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"id": cat_id, "name": "General", "description": "General discussion"},
            ]
        )

        try:
            _override_auth("MEMBER")
            with patch(f"{_REPO}.get_pool", return_value=mock_pool):
                resp = await client.get(
                    "/api/v1/categories",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["categories"]) == 1
                assert data["categories"][0]["name"] == "General"
        finally:
            _clear_overrides()


class TestCreateCategory:
    @pytest.mark.anyio
    async def test_create_category(self, client, mock_pool, mock_conn):
        """POST /categories → 201."""
        cat_id = uuid.uuid4()
        mock_conn.fetchval = AsyncMock(return_value=0)  # category_exists = False
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "id": cat_id,
                "name": "Science",
                "description": "Science topics",
            }
        )

        try:
            _override_auth("ADMIN")
            with patch(f"{_REPO}.get_pool", return_value=mock_pool):
                resp = await client.post(
                    "/api/v1/categories",
                    json={"name": "Science", "description": "Science topics"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["name"] == "Science"
        finally:
            _clear_overrides()
