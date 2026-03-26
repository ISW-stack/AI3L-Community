"""Tests for F-60, F-61, F-64 functional bug fixes.

F-60: Guest invite code consumed only AFTER capacity checks pass.
F-61: find_by_sig() excludes forms from soft-deleted SIGs.
F-64: DM text cleanup uses DELETE...RETURNING for idempotent char decrements.
"""

import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from httpx import AsyncClient


# ── Module prefix for endpoint patches ──
_EP = "app.api.v1.endpoints.auth"


# ===========================================================================
# F-60: Guest invite code ordering
# ===========================================================================


class TestF60InviteCodeOrdering:
    """Invite code must NOT be consumed until guest capacity checks pass."""

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.consume_invite_code", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.guest_login", new_callable=AsyncMock, return_value=("tok", "jti", 2700))
    @patch(f"{_EP}.increment_guest_ip_counter", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    async def test_invite_code_consumed_after_capacity_check(
        self,
        mock_invite,
        mock_captcha,
        mock_ip_incr,
        mock_guest,
        mock_consume,
        mock_rl,
        client: AsyncClient,
    ):
        """On success, consume_invite_code is called AFTER guest_login succeeds."""
        mock_invite.return_value = {"code": "INV-OK", "id": uuid.uuid4()}

        resp = await client.post(
            "/api/v1/auth/guest/INV-OK",
            json={"display_name": "Visitor", "captcha_id": "c1", "captcha_code": "ABCD"},
        )
        assert resp.status_code == 200
        # ip_incr called before consume
        mock_ip_incr.assert_called_once()
        mock_guest.assert_called_once()
        mock_consume.assert_called_once()

    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.consume_invite_code", new_callable=AsyncMock)
    @patch(f"{_EP}.increment_guest_ip_counter", new_callable=AsyncMock, return_value=False)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    async def test_ip_limit_does_not_consume_invite_code(
        self,
        mock_invite,
        mock_captcha,
        mock_ip_incr,
        mock_consume,
        mock_rl,
        client: AsyncClient,
    ):
        """When per-IP limit is exceeded, invite code is NOT consumed."""
        mock_invite.return_value = {"code": "INV-SAVE", "id": uuid.uuid4()}

        resp = await client.post(
            "/api/v1/auth/guest/INV-SAVE",
            json={"display_name": "Visitor", "captcha_id": "c1", "captcha_code": "ABCD"},
        )
        assert resp.status_code == 429
        # The invite code should NOT have been consumed
        mock_consume.assert_not_called()

    @patch(f"{_EP}.decrement_guest_ip_counter", new_callable=AsyncMock)
    @patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.consume_invite_code", new_callable=AsyncMock)
    @patch(f"{_EP}.guest_login", new_callable=AsyncMock, return_value=None)
    @patch(f"{_EP}.increment_guest_ip_counter", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=True)
    @patch(f"{_EP}.get_invite_code", new_callable=AsyncMock)
    async def test_capacity_full_does_not_consume_invite_code(
        self,
        mock_invite,
        mock_captcha,
        mock_ip_incr,
        mock_guest,
        mock_consume,
        mock_rl,
        mock_dec_ip,
        client: AsyncClient,
    ):
        """When global guest capacity is full, invite code is NOT consumed."""
        mock_invite.return_value = {"code": "INV-SAVE2", "id": uuid.uuid4()}

        resp = await client.post(
            "/api/v1/auth/guest/INV-SAVE2",
            json={"display_name": "Visitor", "captcha_id": "c1", "captcha_code": "ABCD"},
        )
        assert resp.status_code == 429
        assert resp.json()["detail"]["code"] == "AUTH_003"
        # Invite code NOT consumed, IP counter decremented
        mock_consume.assert_not_called()
        mock_dec_ip.assert_called_once()


# ===========================================================================
# F-61: find_by_sig excludes soft-deleted SIGs
# ===========================================================================


class TestF61FormRepoDeletedSig:
    """find_by_sig must exclude forms when the parent SIG is soft-deleted."""

    @pytest.mark.anyio
    async def test_find_by_sig_joins_sigs_table(self):
        """SQL queries in find_by_sig reference sigs table with is_deleted check."""
        import inspect

        from app.repositories import form_repo

        source = inspect.getsource(form_repo.find_by_sig)
        # Both the count and the main query must join sigs
        assert "JOIN sigs" in source, "find_by_sig must JOIN sigs table"
        assert "s.is_deleted = false" in source, "find_by_sig must filter on s.is_deleted"

    @pytest.mark.anyio
    async def test_find_by_sig_deleted_sig_returns_empty(self):
        """When SIG is soft-deleted, find_by_sig returns no forms."""
        sig_id = uuid.uuid4()

        mock_conn = MagicMock()
        # SIG is deleted → count returns 0, no rows
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import find_by_sig

            results, total = await find_by_sig(sig_id)

        assert total == 0
        assert results == []
        # Verify the SQL contains the sigs join
        count_sql = mock_conn.fetchval.call_args[0][0]
        assert "sigs" in count_sql
        assert "is_deleted = false" in count_sql

    @pytest.mark.anyio
    async def test_find_by_sig_active_sig_returns_forms(self):
        """When SIG is active, find_by_sig returns its forms normally."""
        sig_id = uuid.uuid4()
        form_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_row = MagicMock()
        row_dict = {
            "id": form_id,
            "sig_id": sig_id,
            "created_by": user_id,
            "is_deleted": False,
            "creator_display_name": "Alice",
            "response_count": 5,
        }
        mock_row.__iter__ = lambda self: iter(row_dict.items())
        mock_row.keys = lambda: row_dict.keys()
        mock_row.__getitem__ = lambda self, k: row_dict[k]

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acq

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import find_by_sig

            results, total = await find_by_sig(sig_id)

        assert total == 1
        assert len(results) == 1
        form_data, response_count = results[0]
        assert response_count == 5
        assert form_data["id"] == form_id


# ===========================================================================
# F-64: DM text cleanup idempotency via DELETE...RETURNING
# ===========================================================================

# Celery module mock (must precede imports of app.tasks.*)
@pytest.fixture(autouse=True)
def _celery_modules():
    """Inject fake celery modules so task imports succeed without a broker."""
    celery_mod = types.ModuleType("celery")
    celery_result_mod = types.ModuleType("celery.result")
    celery_mod.result = celery_result_mod
    celery_mod.shared_task = lambda **kw: (lambda fn: fn)

    celery_app_mod = types.ModuleType("app.celery_app")
    mock_celery_app = MagicMock()
    mock_celery_app.task = lambda *a, **kw: (lambda fn: fn)
    celery_app_mod.celery = mock_celery_app

    saved = {}
    for key in ("celery", "celery.result", "app.celery_app"):
        saved[key] = sys.modules.get(key)

    sys.modules["celery"] = celery_mod
    sys.modules["celery.result"] = celery_result_mod
    sys.modules["app.celery_app"] = celery_app_mod

    yield

    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val

    for mod_name in list(sys.modules):
        if mod_name.startswith("app.tasks."):
            del sys.modules[mod_name]


class TestF64DmTextCleanupIdempotent:
    """DM text cleanup must use DELETE...RETURNING for idempotent char decrements."""

    @pytest.mark.anyio
    async def test_cleanup_text_uses_delete_returning(self):
        """Source code of _cleanup_text must use DELETE...RETURNING pattern."""
        import importlib
        import inspect

        mod = importlib.import_module("app.tasks.dm_cleanup")
        source = inspect.getsource(mod._cleanup_text)
        assert "RETURNING" in source, "_cleanup_text must use DELETE...RETURNING"
        # Should NOT pre-compute char lengths from the find result
        assert "len(msg" not in source, (
            "_cleanup_text should not compute lengths from find results; "
            "it should use SQL LENGTH from RETURNING"
        )

    @pytest.mark.anyio
    async def test_cleanup_text_double_run_no_spurious_decrement(self):
        """Second run finds messages already deleted — RETURNING is empty, no decrement."""
        msg_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        expired_msgs = [
            {"id": msg_id, "conversation_id": conv_id, "content": "Hello!"}
        ]

        # First call to find_expired returns messages, second returns empty (loop exit)
        mock_find = AsyncMock(side_effect=[expired_msgs, []])

        # DELETE...RETURNING returns nothing (messages already deleted by prior run)
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])  # empty RETURNING
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool_obj = MagicMock()
        mock_pool_obj.acquire.return_value = mock_acq

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_text_messages", mock_find),
            patch("app.core.database.get_pool", return_value=mock_pool_obj),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        # No messages were actually deleted (already gone), so count is 0
        assert result["deleted"] == 0
        # execute should NOT have been called for UPDATE (no chars to decrement)
        for call in mock_conn.execute.call_args_list:
            sql = call[0][0] if call[0] else ""
            assert "UPDATE conversations" not in sql, (
                "Should not decrement total_chars when DELETE...RETURNING is empty"
            )

    @pytest.mark.anyio
    async def test_cleanup_text_normal_delete_decrements_by_returned_length(self):
        """Normal cleanup: chars decremented based on RETURNING content lengths."""
        msg_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        expired_msgs = [
            {"id": msg_id, "conversation_id": conv_id, "content": "12345"}
        ]

        mock_find = AsyncMock(side_effect=[expired_msgs, []])

        # DELETE...RETURNING returns the deleted row with content_len
        deleted_row = MagicMock()
        deleted_row.__getitem__ = lambda self, k: {
            "id": msg_id,
            "conversation_id": conv_id,
            "content_len": 5,
        }[k]
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[deleted_row])
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction.return_value = mock_tx
        mock_acq = MagicMock()
        mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool_obj = MagicMock()
        mock_pool_obj.acquire.return_value = mock_acq

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_text_messages", mock_find),
            patch("app.core.database.get_pool", return_value=mock_pool_obj),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        assert result["deleted"] == 1
        # Verify UPDATE was called with the correct char count from RETURNING
        update_calls = [
            c for c in mock_conn.execute.call_args_list
            if "UPDATE conversations" in (c[0][0] if c[0] else "")
        ]
        assert len(update_calls) == 1
        # First positional arg after SQL is the char count
        assert update_calls[0][0][1] == 5
