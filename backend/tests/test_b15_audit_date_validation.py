"""B15: Audit log date range validation — date_from/date_to are validated as YYYY-MM-DD."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest


class TestAuditLogDateValidation:
    """GET /users/admin/audit-logs date params are validated by FastAPI."""

    def _override_super_admin(self, user_id: str | None = None) -> str:
        from app.core.deps import get_current_user
        from app.main import app

        uid = user_id or str(uuid.uuid4())
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": uid,
            "role": "SUPER_ADMIN",
            "jti": "jti-1",
        }
        return uid

    def _clear(self) -> None:
        from app.main import app

        app.dependency_overrides.clear()

    @patch(
        "app.api.v1.endpoints.users.list_audit_logs",
        new_callable=AsyncMock,
        return_value=([], 0),
    )
    async def test_valid_dates_pass(self, mock_list: AsyncMock, client: AsyncMock) -> None:
        """Valid YYYY-MM-DD dates should pass and be forwarded to the service."""
        self._override_super_admin()
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs?date_from=2025-01-01&date_to=2025-12-31",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            mock_list.assert_called_once_with(
                page=1,
                page_size=20,
                user_id_filter=None,
                date_from="2025-01-01",
                date_to="2025-12-31",
            )
        finally:
            self._clear()

    async def test_invalid_date_from_returns_422(self, client: AsyncMock) -> None:
        """Non-date string for date_from should return 422."""
        self._override_super_admin()
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs?date_from=not-a-date",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            self._clear()

    async def test_invalid_date_to_returns_422(self, client: AsyncMock) -> None:
        """Non-date string for date_to should return 422."""
        self._override_super_admin()
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs?date_to=yesterday",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            self._clear()

    async def test_invalid_date_format_returns_422(self, client: AsyncMock) -> None:
        """Date in wrong format (DD-MM-YYYY) should return 422."""
        self._override_super_admin()
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs?date_from=31-12-2025",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            self._clear()

    @patch(
        "app.api.v1.endpoints.users.list_audit_logs",
        new_callable=AsyncMock,
        return_value=([], 0),
    )
    async def test_date_from_after_date_to_returns_422(
        self, mock_list: AsyncMock, client: AsyncMock
    ) -> None:
        """date_from > date_to should return 422."""
        self._override_super_admin()
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs?date_from=2025-12-31&date_to=2025-01-01",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
            data = resp.json()
            assert "date_from" in data["detail"]["message"].lower()
        finally:
            self._clear()

    @patch(
        "app.api.v1.endpoints.users.list_audit_logs",
        new_callable=AsyncMock,
        return_value=([], 0),
    )
    async def test_same_date_from_and_to_passes(
        self, mock_list: AsyncMock, client: AsyncMock
    ) -> None:
        """date_from == date_to should be valid (single day)."""
        self._override_super_admin()
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs?date_from=2025-06-15&date_to=2025-06-15",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
        finally:
            self._clear()

    @patch(
        "app.api.v1.endpoints.users.list_audit_logs",
        new_callable=AsyncMock,
        return_value=([], 0),
    )
    async def test_only_date_from_passes(
        self, mock_list: AsyncMock, client: AsyncMock
    ) -> None:
        """Providing only date_from (no date_to) should be valid."""
        self._override_super_admin()
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs?date_from=2025-01-01",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            mock_list.assert_called_once_with(
                page=1,
                page_size=20,
                user_id_filter=None,
                date_from="2025-01-01",
                date_to=None,
            )
        finally:
            self._clear()

    @patch(
        "app.api.v1.endpoints.users.list_audit_logs",
        new_callable=AsyncMock,
        return_value=([], 0),
    )
    async def test_only_date_to_passes(
        self, mock_list: AsyncMock, client: AsyncMock
    ) -> None:
        """Providing only date_to (no date_from) should be valid."""
        self._override_super_admin()
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs?date_to=2025-12-31",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            mock_list.assert_called_once_with(
                page=1,
                page_size=20,
                user_id_filter=None,
                date_from=None,
                date_to="2025-12-31",
            )
        finally:
            self._clear()
