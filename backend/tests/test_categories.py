"""Tests for categories endpoints — list, create, update, delete."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.categories"
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


def _make_category(cat_id=None, name="Science", description="Science topics"):
    return {
        "id": str(cat_id or uuid.uuid4()),
        "name": name,
        "description": description,
        "post_count": 0,
    }


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

    @pytest.mark.anyio
    async def test_list_categories_empty(self, client, mock_pool, mock_conn):
        """GET /categories → 200 with empty list."""
        mock_conn.fetch = AsyncMock(return_value=[])

        try:
            _override_auth("MEMBER")
            with patch(f"{_REPO}.get_pool", return_value=mock_pool):
                resp = await client.get(
                    "/api/v1/categories",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["categories"] == []
                assert data["total"] == 0
        finally:
            _clear_overrides()


class TestGetCategory:
    @pytest.mark.anyio
    async def test_get_category_success(self, client):
        """GET /categories/{id} → 200 with category and post_count."""
        cat_id = uuid.uuid4()
        cat = _make_category(cat_id=cat_id, name="Science")

        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.get_category_by_id",
                new_callable=AsyncMock,
                return_value=cat,
            ):
                resp = await client.get(
                    f"/api/v1/categories/{cat_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["name"] == "Science"
                assert data["id"] == str(cat_id)
                assert "post_count" in data
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_category_not_found(self, client):
        """GET /categories/{id} → 404 when category does not exist."""
        cat_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(
                f"{_EP}.get_category_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.get(
                    f"/api/v1/categories/{cat_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"]["message"].lower()
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
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_REPO}.get_pool", return_value=mock_pool),
            ):
                resp = await client.post(
                    "/api/v1/categories",
                    json={"name": "Science", "description": "Science topics"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["name"] == "Science"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_category_duplicate(self, client):
        """POST /categories with existing name → 409."""
        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.category_exists", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_category", new_callable=AsyncMock),
            ):
                resp = await client.post(
                    "/api/v1/categories",
                    json={"name": "Science", "description": "Already exists"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                assert "already exists" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_category_forbidden_for_member(self, client):
        """POST /categories as MEMBER → 403."""
        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.create_category", new_callable=AsyncMock):
                resp = await client.post(
                    "/api/v1/categories",
                    json={"name": "Science", "description": "Unauthorized"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestUpdateCategory:
    @pytest.mark.anyio
    async def test_update_category_success(self, client):
        """PUT /categories/{id} → 200 with updated category."""
        cat_id = uuid.uuid4()
        updated_cat = _make_category(cat_id=cat_id, name="Updated Science")

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.update_category",
                    new_callable=AsyncMock,
                    return_value=updated_cat,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/categories/{cat_id}",
                    json={"name": "Updated Science", "description": "Updated description"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["name"] == "Updated Science"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_category_not_found(self, client):
        """PUT /categories/{id} → 404 when category does not exist."""
        cat_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.update_category",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/categories/{cat_id}",
                    json={"name": "Ghost Category"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_category_forbidden_for_member(self, client):
        """PUT /categories/{id} as MEMBER → 403."""
        cat_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.update_category", new_callable=AsyncMock):
                resp = await client.put(
                    f"/api/v1/categories/{cat_id}",
                    json={"name": "Unauthorized"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestDeleteCategory:
    @pytest.mark.anyio
    async def test_delete_category_success(self, client):
        """DELETE /categories/{id} → 204 when category exists."""
        cat_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.delete_category",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/categories/{cat_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_category_not_found(self, client):
        """DELETE /categories/{id} → 404 when category does not exist."""
        cat_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.delete_category",
                    new_callable=AsyncMock,
                    return_value=False,
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/categories/{cat_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_category_forbidden_for_member(self, client):
        """DELETE /categories/{id} as MEMBER → 403."""
        cat_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.delete_category", new_callable=AsyncMock):
                resp = await client.delete(
                    f"/api/v1/categories/{cat_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestCategoryCrudRateLimit:
    @pytest.mark.anyio
    async def test_create_category_rate_limited(self, client):
        """POST /categories → 429 when rate limited."""
        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    "/api/v1/categories",
                    json={"name": "Science", "description": "Science topics"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_category_rate_limited(self, client):
        """PUT /categories/{id} → 429 when rate limited."""
        cat_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.put(
                    f"/api/v1/categories/{cat_id}",
                    json={"name": "Updated"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_category_rate_limited(self, client):
        """DELETE /categories/{id} → 429 when rate limited."""
        cat_id = uuid.uuid4()

        try:
            _override_auth("ADMIN")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(
                    f"/api/v1/categories/{cat_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()
