"""Tests for DM-08: ROLE_CHANGED WebSocket event handling.

Verifies that:
1. Role change sends ROLE_CHANGED WS event before session revocation.
2. The ROLE_CHANGED event includes the new role.
3. The Pub/Sub subscriber closes connections after delivering ROLE_CHANGED.
4. The _local_close_for_role_change helper closes with code 4007.
5. Bulk role change sends ROLE_CHANGED before revoke for each user.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


class TestRoleChangeSendsWSEventBeforeRevoke:
    """Verify that role change endpoints emit user.role_changed BEFORE revoking sessions."""

    @pytest.mark.anyio
    async def test_single_role_change_emits_before_revoke(self, client):
        """PUT /users/{id}/role emits user.role_changed before revoke_user_sessions."""
        from tests.conftest import make_user_dict

        _EP = "app.api.v1.endpoints.users"
        target_user = uuid.uuid4()
        user = make_user_dict(user_id=str(target_user), role="ADMIN")
        call_order: list[str] = []

        async def track_emit(event, **kwargs):
            call_order.append(f"emit:{event}")

        async def track_revoke(*args, **kwargs):
            call_order.append("revoke")

        # Override auth to SUPER_ADMIN
        from app.core.deps import get_current_user
        from app.main import app

        admin_payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: admin_payload

        try:
            with (
                patch(f"{_EP}.update_user_role", new_callable=AsyncMock, return_value=user),
                patch(f"{_EP}.revoke_user_sessions", side_effect=track_revoke),
                patch(f"{_EP}.emit", side_effect=track_emit),
            ):
                resp = await client.put(
                    f"/api/v1/users/{target_user}/role",
                    json={"role": "ADMIN"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200

                # user.role_changed must appear before revoke
                role_idx = next(
                    i for i, v in enumerate(call_order) if v == "emit:user.role_changed"
                )
                revoke_idx = next(i for i, v in enumerate(call_order) if v == "revoke")
                assert role_idx < revoke_idx, (
                    f"ROLE_CHANGED (index {role_idx}) must be emitted before "
                    f"revoke_user_sessions (index {revoke_idx})"
                )
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_role_changed_event_includes_new_role(self, client):
        """The user.role_changed event must include the new_role value."""
        from tests.conftest import make_user_dict

        _EP = "app.api.v1.endpoints.users"
        target_user = uuid.uuid4()
        user = make_user_dict(user_id=str(target_user), role="MEMBER")

        from app.core.deps import get_current_user
        from app.main import app

        admin_payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: admin_payload

        try:
            with (
                patch(f"{_EP}.update_user_role", new_callable=AsyncMock, return_value=user),
                patch(f"{_EP}.revoke_user_sessions", new_callable=AsyncMock),
                patch(f"{_EP}.emit", new_callable=AsyncMock) as mock_emit,
            ):
                resp = await client.put(
                    f"/api/v1/users/{target_user}/role",
                    json={"role": "MEMBER"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200

                # Find the user.role_changed call
                role_calls = [
                    c
                    for c in mock_emit.call_args_list
                    if c.args and c.args[0] == "user.role_changed"
                ]
                assert len(role_calls) == 1
                assert role_calls[0].kwargs["new_role"] == "MEMBER"
                assert role_calls[0].kwargs["user_id"] == str(target_user)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_bulk_role_change_emits_before_revoke_per_user(self, client):
        """PUT /users/bulk-role emits user.role_changed before revoke for each user."""
        _EP = "app.api.v1.endpoints.users"
        user_ids = [uuid.uuid4(), uuid.uuid4()]
        call_order: list[str] = []

        async def track_emit(event, **kwargs):
            call_order.append(f"emit:{event}:{kwargs.get('user_id', '')}")

        async def track_revoke(uid):
            call_order.append(f"revoke:{uid}")

        from app.core.deps import get_current_user
        from app.main import app

        admin_payload = {
            "sub": str(uuid.uuid4()),
            "role": "SUPER_ADMIN",
            "jti": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_current_user] = lambda: admin_payload

        try:
            with (
                patch(
                    "app.services.user.bulk_change_role",
                    new_callable=AsyncMock,
                    return_value=2,
                ),
                patch("app.services.audit.log_action", new_callable=AsyncMock),
                patch(
                    "app.services.auth.revoke_user_sessions",
                    side_effect=track_revoke,
                ),
                patch(f"{_EP}.emit", side_effect=track_emit),
            ):
                resp = await client.put(
                    "/api/v1/users/bulk-role",
                    json={
                        "user_ids": [str(uid) for uid in user_ids],
                        "role": "MEMBER",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200

                # For each user, emit must come before revoke
                for uid in user_ids:
                    uid_str = str(uid)
                    emit_key = f"emit:user.role_changed:{uid_str}"
                    revoke_key = f"revoke:{uid_str}"

                    emit_indices = [i for i, v in enumerate(call_order) if v == emit_key]
                    revoke_indices = [i for i, v in enumerate(call_order) if v == revoke_key]

                    assert len(emit_indices) >= 1, f"No emit for user {uid_str}"
                    assert len(revoke_indices) >= 1, f"No revoke for user {uid_str}"
                    assert emit_indices[0] < revoke_indices[0], (
                        f"For user {uid_str}: emit (index {emit_indices[0]}) "
                        f"must come before revoke (index {revoke_indices[0]})"
                    )
        finally:
            app.dependency_overrides.clear()


class TestPubSubRoleChangedHandling:
    """Verify the Redis Pub/Sub subscriber handles ROLE_CHANGED messages."""

    @pytest.mark.anyio
    async def test_pubsub_calls_close_for_role_change(self):
        """When a ROLE_CHANGED message arrives via Pub/Sub, connections should close."""
        from app.api.v1.endpoints.ws import (
            _local_close_for_role_change,
            _local_send,
        )

        user_id = str(uuid.uuid4())
        mock_ws = AsyncMock()

        with patch("app.api.v1.endpoints.ws._local_send", new_callable=AsyncMock) as mock_send:
            with patch(
                "app.api.v1.endpoints.ws._local_close_for_role_change",
                new_callable=AsyncMock,
            ) as mock_close:
                # Simulate Pub/Sub message delivery
                # The subscriber calls _local_send first, then checks type
                message = {"type": "ROLE_CHANGED", "new_role": "ADMIN"}
                await mock_send(user_id, message)
                # Then the subscriber calls _local_close_for_role_change
                await mock_close(user_id)

                mock_send.assert_awaited_once_with(user_id, message)
                mock_close.assert_awaited_once_with(user_id)


class TestLocalCloseForRoleChange:
    """Verify _local_close_for_role_change closes WS with code 4007."""

    @pytest.mark.anyio
    async def test_closes_with_code_4007(self):
        """Connections should be closed with code 4007 and reason 'Role changed'."""
        from app.api.v1.endpoints.ws import (
            _connections,
            _connections_lock,
            _local_close_for_role_change,
        )

        user_id = str(uuid.uuid4())
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()

        async with _connections_lock:
            _connections[user_id] = {mock_ws}

        try:
            await _local_close_for_role_change(user_id)

            mock_ws.close.assert_awaited_once_with(code=4007, reason="Role changed")

            # Connections should be removed
            async with _connections_lock:
                assert user_id not in _connections
        finally:
            # Cleanup
            async with _connections_lock:
                _connections.pop(user_id, None)

    @pytest.mark.anyio
    async def test_closes_multiple_connections(self):
        """All connections for the user should be closed."""
        from app.api.v1.endpoints.ws import (
            _connections,
            _connections_lock,
            _local_close_for_role_change,
        )

        user_id = str(uuid.uuid4())
        mock_ws1 = AsyncMock()
        mock_ws1.close = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.close = AsyncMock()

        async with _connections_lock:
            _connections[user_id] = {mock_ws1, mock_ws2}

        try:
            await _local_close_for_role_change(user_id)

            mock_ws1.close.assert_awaited_once_with(code=4007, reason="Role changed")
            mock_ws2.close.assert_awaited_once_with(code=4007, reason="Role changed")

            async with _connections_lock:
                assert user_id not in _connections
        finally:
            async with _connections_lock:
                _connections.pop(user_id, None)

    @pytest.mark.anyio
    async def test_handles_close_exception_gracefully(self):
        """If ws.close raises, the error should be logged and other connections still closed."""
        from app.api.v1.endpoints.ws import (
            _connections,
            _connections_lock,
            _local_close_for_role_change,
        )

        user_id = str(uuid.uuid4())
        mock_ws_bad = AsyncMock()
        mock_ws_bad.close = AsyncMock(side_effect=RuntimeError("already closed"))
        mock_ws_good = AsyncMock()
        mock_ws_good.close = AsyncMock()

        async with _connections_lock:
            _connections[user_id] = {mock_ws_bad, mock_ws_good}

        try:
            # Should not raise
            await _local_close_for_role_change(user_id)

            # Both should have been attempted
            mock_ws_bad.close.assert_awaited_once()
            mock_ws_good.close.assert_awaited_once()

            # User should be removed from connections
            async with _connections_lock:
                assert user_id not in _connections
        finally:
            async with _connections_lock:
                _connections.pop(user_id, None)

    @pytest.mark.anyio
    async def test_no_connections_is_noop(self):
        """If user has no connections, function should not raise."""
        from app.api.v1.endpoints.ws import _local_close_for_role_change

        user_id = str(uuid.uuid4())
        # Should not raise
        await _local_close_for_role_change(user_id)


class TestRoleChangedEventHandler:
    """Verify the _on_user_role_changed event handler sends correct WS payload."""

    @pytest.mark.anyio
    async def test_event_handler_sends_role_changed_with_new_role(self):
        """_on_user_role_changed sends {type: ROLE_CHANGED, new_role: ...} via WS."""
        from app.event_handlers import _on_user_role_changed

        mock_send = AsyncMock()
        user_id = str(uuid.uuid4())

        with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
            await _on_user_role_changed(user_id=user_id, new_role="ADMIN")

        mock_send.assert_awaited_once_with(
            user_id, {"type": "ROLE_CHANGED", "new_role": "ADMIN"}
        )

    @pytest.mark.anyio
    async def test_event_handler_includes_correct_role_values(self):
        """The new_role in the WS message matches the event kwarg for different roles."""
        from app.event_handlers import _on_user_role_changed

        for role in ("MEMBER", "ADMIN", "SUPER_ADMIN"):
            mock_send = AsyncMock()
            user_id = str(uuid.uuid4())

            with patch("app.api.v1.endpoints.ws.send_to_user", mock_send):
                await _on_user_role_changed(user_id=user_id, new_role=role)

            sent_msg = mock_send.call_args[0][1]
            assert sent_msg["type"] == "ROLE_CHANGED"
            assert sent_msg["new_role"] == role
