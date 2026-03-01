"""Tests for app.services.audit — log_action, list_audit_logs, endpoint access control."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestLogAction:
    @patch("app.repositories.audit_repo.get_pool")
    async def test_log_action(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.audit import log_action

        mock_get_pool.return_value = mock_pool

        await log_action(str(uuid.uuid4()), "LOGIN", ip_address="127.0.0.1")
        mock_conn.execute.assert_called_once()

    @patch("app.repositories.audit_repo.get_pool")
    async def test_log_action_with_target(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.audit import log_action

        mock_get_pool.return_value = mock_pool
        target_id = str(uuid.uuid4())

        await log_action(
            str(uuid.uuid4()), "BAN", target_type="user", target_id=target_id, ip_address="10.0.0.1"
        )
        mock_conn.execute.assert_called_once()

    @patch("app.repositories.audit_repo.get_pool")
    async def test_log_action_handles_db_error(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.audit import log_action

        mock_conn.execute.side_effect = Exception("DB error")
        mock_get_pool.return_value = mock_pool

        # Should not raise — best-effort
        await log_action(str(uuid.uuid4()), "LOGIN")


class TestListAuditLogs:
    @patch("app.repositories.audit_repo.get_pool")
    async def test_list_audit_logs(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.audit import list_audit_logs

        now = datetime.now(timezone.utc)
        mock_conn.fetchval.return_value = 2
        mock_conn.fetch.return_value = [
            {
                "id": uuid.uuid4(),
                "user_id": uuid.uuid4(),
                "username": "alice",
                "display_name": "Alice",
                "action": "LOGIN",
                "target_type": None,
                "target_id": None,
                "ip_address": "127.0.0.1",
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "user_id": uuid.uuid4(),
                "username": "bob",
                "display_name": "Bob",
                "action": "LOGOUT",
                "target_type": None,
                "target_id": None,
                "ip_address": "10.0.0.1",
                "created_at": now,
            },
        ]
        mock_get_pool.return_value = mock_pool

        logs, total = await list_audit_logs(page=1, page_size=50)
        assert total == 2
        assert len(logs) == 2
        assert logs[0]["action"] == "LOGIN"

    @patch("app.repositories.audit_repo.get_pool")
    async def test_list_audit_logs_with_user_filter(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.audit import list_audit_logs

        mock_conn.fetchval.return_value = 0
        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        logs, total = await list_audit_logs(page=1, page_size=50, user_id_filter=str(uuid.uuid4()))
        assert total == 0
        assert logs == []


class TestAuditLogsEndpoint:
    async def test_audit_logs_endpoint_super_admin_only(self, client: AsyncClient):
        """Non-SUPER_ADMIN should get 403."""
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "ADMIN", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.api.v1.endpoints.users.list_audit_logs", new_callable=AsyncMock, return_value=([], 0))
    async def test_audit_logs_endpoint_success(self, mock_list, client: AsyncClient):
        from app.core.deps import get_current_user
        from app.main import app

        payload = {"sub": str(uuid.uuid4()), "role": "SUPER_ADMIN", "jti": "jti-1"}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.get(
                "/api/v1/users/admin/audit-logs",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "logs" in data
            assert "total" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)
