"""Tests for category name UNIQUE constraint handling (N1 fix)."""

import uuid
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

_EP = "app.api.v1.endpoints.categories"


def _override_auth(role="ADMIN", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestCreateCategoryUniqueConstraint:
    @pytest.mark.anyio
    async def test_duplicate_name_returns_409(self, client):
        """POST /categories with duplicate name triggers UniqueViolationError → 409."""
        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_category",
                    new_callable=AsyncMock,
                    side_effect=asyncpg.UniqueViolationError(),
                ),
            ):
                resp = await client.post(
                    "/api/v1/categories",
                    json={"name": "Science", "description": "Duplicate"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 409
                assert "already exists" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_category_success_no_precheck(self, client):
        """POST /categories succeeds without pre-check when no constraint violation."""
        cat_id = uuid.uuid4()
        try:
            _override_auth("ADMIN")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_EP}.create_category",
                    new_callable=AsyncMock,
                    return_value={
                        "id": cat_id,
                        "name": "NewCategory",
                        "description": "Desc",
                    },
                ),
            ):
                resp = await client.post(
                    "/api/v1/categories",
                    json={"name": "NewCategory", "description": "Desc"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["name"] == "NewCategory"
        finally:
            _clear_overrides()
