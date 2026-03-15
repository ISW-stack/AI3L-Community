"""Tests for Bug #12: user.role_changed event handler."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.event_handlers import _on_user_role_changed, register_all


class TestOnUserRoleChanged:
    """Verify the _on_user_role_changed handler sends a WebSocket message."""

    @pytest.mark.anyio
    async def test_sends_ws_message_on_role_change(self):
        """Handler should call send_to_user with ROLE_CHANGED type and new role."""
        mock_send = AsyncMock()
        user_id = str(uuid.uuid4())

        with patch("app.event_handlers.send_to_user", mock_send, create=True):
            with patch(
                "app.api.v1.endpoints.ws.send_to_user", mock_send
            ):
                await _on_user_role_changed(user_id=user_id, new_role="ADMIN")

        mock_send.assert_awaited_once_with(
            user_id, {"type": "ROLE_CHANGED", "new_role": "ADMIN"}
        )

    @pytest.mark.anyio
    async def test_sends_correct_role_value(self):
        """The new_role value in the WS message should match what was passed."""
        mock_send = AsyncMock()
        user_id = str(uuid.uuid4())

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            await _on_user_role_changed(user_id=user_id, new_role="MEMBER")

        call_args = mock_send.call_args
        assert call_args[0][1]["new_role"] == "MEMBER"

    @pytest.mark.anyio
    async def test_reraises_ws_exception_for_event_bus_retry(self):
        """If send_to_user raises, the handler should re-raise for event bus retry."""
        mock_send = AsyncMock(side_effect=ConnectionError("WS unavailable"))
        user_id = str(uuid.uuid4())

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            with pytest.raises(ConnectionError, match="WS unavailable"):
                await _on_user_role_changed(user_id=user_id, new_role="ADMIN")

    @pytest.mark.anyio
    async def test_logs_error_on_ws_failure(self):
        """On WS failure, the handler should log an error with exc_info before re-raising."""
        mock_send = AsyncMock(side_effect=RuntimeError("WS down"))
        user_id = str(uuid.uuid4())

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            with patch("app.event_handlers.logger") as mock_logger:
                with pytest.raises(RuntimeError):
                    await _on_user_role_changed(user_id=user_id, new_role="ADMIN")

                mock_logger.error.assert_called_once()
                call_kwargs = mock_logger.error.call_args
                assert call_kwargs.kwargs.get("exc_info") is True

    @pytest.mark.anyio
    async def test_accepts_extra_kwargs(self):
        """Handler should accept and ignore extra keyword arguments (**_kwargs)."""
        mock_send = AsyncMock()

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            await _on_user_role_changed(
                user_id=str(uuid.uuid4()),
                new_role="ADMIN",
                extra_field="should be ignored",
            )

        mock_send.assert_awaited_once()


class TestRoleChangedRegistration:
    """Verify user.role_changed is registered in register_all()."""

    def test_register_all_includes_role_changed(self):
        """register_all() should register a handler for user.role_changed."""
        from app.core.event_bus import _handlers, clear

        clear()
        register_all()

        assert "user.role_changed" in _handlers
        assert len(_handlers["user.role_changed"]) == 1
        assert _handlers["user.role_changed"][0] is _on_user_role_changed

        clear()
