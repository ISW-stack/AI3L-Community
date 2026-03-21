"""Tests for _on_sig_role_changed event handler and emit calls in sig service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.event_handlers import _on_sig_role_changed


# Shared Redis mock helper for tests that call invalidate_org_chart_cache()
def _make_redis_mock():
    redis = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    return redis


class TestOnSigRoleChanged:
    """Unit tests for _on_sig_role_changed handler."""

    @pytest.mark.anyio
    async def test_sends_ws_message_on_demote(self):
        """Handler sends SIG_ROLE_CHANGED with new_role=MEMBER when demoted."""
        user_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        mock_send = AsyncMock()

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            await _on_sig_role_changed(user_id=user_id, sig_id=sig_id, new_role="MEMBER")

        mock_send.assert_awaited_once_with(
            user_id,
            {"type": "SIG_ROLE_CHANGED", "sig_id": sig_id, "new_role": "MEMBER"},
        )

    @pytest.mark.anyio
    async def test_sends_ws_message_on_promote(self):
        """Handler sends SIG_ROLE_CHANGED with new_role=SUB_ADMIN when promoted."""
        user_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())
        mock_send = AsyncMock()

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            await _on_sig_role_changed(user_id=user_id, sig_id=sig_id, new_role="SUB_ADMIN")

        mock_send.assert_awaited_once_with(
            user_id,
            {"type": "SIG_ROLE_CHANGED", "sig_id": sig_id, "new_role": "SUB_ADMIN"},
        )

    @pytest.mark.anyio
    async def test_reraises_on_send_failure(self):
        """Handler re-raises so the event bus can retry."""
        mock_send = AsyncMock(side_effect=RuntimeError("WS unavailable"))

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            with pytest.raises(RuntimeError, match="WS unavailable"):
                await _on_sig_role_changed(
                    user_id=str(uuid.uuid4()),
                    sig_id=str(uuid.uuid4()),
                    new_role="MEMBER",
                )

    @pytest.mark.anyio
    async def test_ignores_extra_kwargs(self):
        """Handler accepts **_kwargs without error (event bus passes extra fields)."""
        mock_send = AsyncMock()

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            await _on_sig_role_changed(
                user_id=str(uuid.uuid4()),
                sig_id=str(uuid.uuid4()),
                new_role="MEMBER",
                extra_field="ignored",
            )

        assert mock_send.await_count == 1


class TestSigServiceEmitsRoleChangedEvent:
    """Verify demote_sub_admin and assign_sub_admin emit sig.role_changed."""

    def _make_member_row(self, sig_id: uuid.UUID, user_id: uuid.UUID, role: str) -> dict:
        return {
            "id": uuid.uuid4(),
            "sig_id": sig_id,
            "user_id": user_id,
            "role": role,
            "joined_at": None,
            "username": "testuser",
            "display_name": "Test User",
            "avatar_url": None,
            "is_deleted": False,
        }

    @pytest.mark.anyio
    async def test_demote_sub_admin_emits_event(self):
        """demote_sub_admin emits sig.role_changed with new_role=MEMBER."""
        from app.services.sig import demote_sub_admin

        sig_id = uuid.uuid4()
        user_id = uuid.uuid4()
        caller_id = uuid.uuid4()
        row = self._make_member_row(sig_id, user_id, "MEMBER")

        mock_conn = MagicMock()
        mock_conn.transaction = MagicMock(return_value=_AsyncContextManager())
        mock_conn.fetchrow = AsyncMock(return_value={"role": "SUB_ADMIN"})

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=_AsyncContextManager(mock_conn))

        mock_emit = AsyncMock()
        mock_row_to_member = AsyncMock(return_value=row)

        with (
            patch("app.services.sig.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.sig_repo.get_member_role_in_conn",
                AsyncMock(return_value="SUB_ADMIN"),
            ),
            patch(
                "app.repositories.sig_repo.update_member_role_in_conn", AsyncMock(return_value=row)
            ),
            patch("app.services.sig.emit", mock_emit),
            patch("app.services.sig.async_row_to_member", mock_row_to_member),
            patch("app.core.redis.get_redis", return_value=_make_redis_mock()),
        ):
            await demote_sub_admin(
                sig_id,
                str(user_id),
                caller_id=str(caller_id),
                caller_role="SUPER_ADMIN",
            )

        mock_emit.assert_awaited_once_with(
            "sig.role_changed",
            user_id=str(user_id),
            sig_id=str(sig_id),
            new_role="MEMBER",
        )

    @pytest.mark.anyio
    async def test_assign_sub_admin_emits_event(self):
        """assign_sub_admin emits sig.role_changed with new_role=SUB_ADMIN."""
        from app.services.sig import assign_sub_admin

        sig_id = uuid.uuid4()
        user_id = uuid.uuid4()
        caller_id = uuid.uuid4()
        row = self._make_member_row(sig_id, user_id, "SUB_ADMIN")

        mock_emit = AsyncMock()
        mock_row_to_member = AsyncMock(return_value=row)

        with (
            patch(
                "app.repositories.sig_repo.get_member_role_in_conn",
                AsyncMock(return_value="MEMBER"),
            ),
            patch(
                "app.repositories.sig_repo.update_member_role_in_conn", AsyncMock(return_value=row)
            ),
            patch("app.repositories.sig_repo.count_admins", AsyncMock(return_value=1)),
            patch("app.services.sig.get_pool") as mock_get_pool,
            patch("app.services.sig.emit", mock_emit),
            patch("app.services.sig.async_row_to_member", mock_row_to_member),
            patch("app.core.redis.get_redis", return_value=_make_redis_mock()),
        ):
            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=_AsyncContextManager(MagicMock()))
            mock_get_pool.return_value = mock_pool

            conn_mock = MagicMock()
            conn_mock.transaction = MagicMock(return_value=_AsyncContextManager())
            conn_mock.fetchrow = AsyncMock(return_value={"role": "MEMBER"})
            mock_pool.acquire = MagicMock(return_value=_AsyncContextManager(conn_mock))

            await assign_sub_admin(
                sig_id,
                str(user_id),
                caller_id=str(caller_id),
                caller_role="SUPER_ADMIN",
            )

        mock_emit.assert_awaited_once_with(
            "sig.role_changed",
            user_id=str(user_id),
            sig_id=str(sig_id),
            new_role="SUB_ADMIN",
        )


class _AsyncContextManager:
    """Minimal async context manager for mocking asyncpg pool.acquire / conn.transaction."""

    def __init__(self, value=None):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *_):
        pass
