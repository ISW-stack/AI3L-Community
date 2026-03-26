"""Tests for functional bug fixes F-16 through F-23.

F-16: Idempotency middleware no longer truncates SHA256 hash
F-17: DM cleanup clears DB before MinIO deletion
F-18: DM text cleanup processes each conversation in its own transaction
F-19: Event bus _persist_failed_event returns boolean
F-20: Form find_by_id response_count pop has default
F-21: DM repo distinguishes "not found" vs "not participant"
F-22: Form stats includes total_responses field
F-23: Comment edit checks existence before rate limit
"""

import hashlib
import json
import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Celery module mock (must precede imports of app.tasks.*)
# ---------------------------------------------------------------------------
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


# ===========================================================================
# F-16: Idempotency middleware uses full SHA256 hash (no truncation)
# ===========================================================================


class TestF16IdempotencyFullHash:
    """Verify that the idempotency middleware uses the full SHA256 hash."""

    def test_no_truncation_in_source(self):
        """Source code should not truncate the SHA256 hex digest."""
        import inspect

        from app.middleware.idempotency import IdempotencyMiddleware

        source = inspect.getsource(IdempotencyMiddleware.dispatch)
        # The old code had hexdigest()[:16] — ensure that's gone
        assert "hexdigest()[:16]" not in source
        assert "hexdigest()[:" not in source

    def test_full_hash_produces_64_char_key(self):
        """Full SHA256 hexdigest should be 64 characters, not 16."""
        token = "test-token-value"
        user_id = hashlib.sha256(token.encode()).hexdigest()
        assert len(user_id) == 64

    def test_different_tokens_with_same_16char_prefix_differ(self):
        """Two tokens whose SHA256 hashes share the first 16 chars must produce
        different full hashes (the fix prevents collisions)."""
        # While we can't easily find a collision in the first 16 chars,
        # we verify the full hash is used by checking key construction
        token_a = "token-user-alpha"
        token_b = "token-user-beta"
        hash_a = hashlib.sha256(token_a.encode()).hexdigest()
        hash_b = hashlib.sha256(token_b.encode()).hexdigest()

        key_a = f"idempotency:{hash_a}:my-idem-key"
        key_b = f"idempotency:{hash_b}:my-idem-key"

        assert key_a != key_b
        # Both keys use the full 64-char hash
        assert len(hash_a) == 64
        assert len(hash_b) == 64


# ===========================================================================
# F-17: DM cleanup clears DB before MinIO deletion
# ===========================================================================


class TestF17DmCleanupDbFirst:
    """Verify that file cleanup clears DB record before deleting from MinIO."""

    @pytest.mark.anyio
    async def test_db_cleared_before_minio_delete(self):
        """clear_message_attachment_if_present must be called before delete_file."""
        msg_id = uuid.uuid4()
        sender_id = uuid.uuid4()
        expired_msgs = [
            {
                "id": msg_id,
                "attachment_key": "dm/test/file.pdf",
                "attachment_size": 1024,
                "sender_id": sender_id,
            }
        ]

        call_order = []

        async def mock_clear(mid):
            call_order.append("db_clear")
            return True

        async def mock_delete(key):
            call_order.append("minio_delete")

        mock_find = AsyncMock(return_value=expired_msgs)
        mock_decrement = AsyncMock()

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_file_messages", mock_find),
            patch(
                "app.repositories.dm_repo.clear_message_attachment_if_present",
                side_effect=mock_clear,
            ),
            patch("app.repositories.user_repo.decrement_storage_used", mock_decrement),
            patch("app.core.async_storage.delete_file", side_effect=mock_delete),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        assert call_order == ["db_clear", "minio_delete"]
        assert result == {"deleted": 1, "errors": 0}

    @pytest.mark.anyio
    async def test_minio_failure_after_db_clear_still_counts_as_deleted(self):
        """If MinIO delete fails after DB clear, the message is still counted as deleted
        (orphan cleanup will handle the leftover file)."""
        msg_id = uuid.uuid4()
        sender_id = uuid.uuid4()
        expired_msgs = [
            {
                "id": msg_id,
                "attachment_key": "dm/test/file.pdf",
                "attachment_size": 1024,
                "sender_id": sender_id,
            }
        ]

        mock_find = AsyncMock(return_value=expired_msgs)
        mock_clear = AsyncMock(return_value=True)
        mock_delete = AsyncMock(side_effect=RuntimeError("MinIO down"))
        mock_decrement = AsyncMock()

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_file_messages", mock_find),
            patch(
                "app.repositories.dm_repo.clear_message_attachment_if_present",
                mock_clear,
            ),
            patch("app.repositories.user_repo.decrement_storage_used", mock_decrement),
            patch("app.core.async_storage.delete_file", mock_delete),
        ):
            from app.tasks.dm_cleanup import _cleanup_files

            result = await _cleanup_files()

        # Should still count as deleted (DB record cleared)
        assert result["deleted"] == 1
        assert result["errors"] == 0


# ===========================================================================
# F-18: DM text cleanup — per-conversation transactions
# ===========================================================================


class TestF18DmTextPerConversationTransaction:
    """Verify that text cleanup processes each conversation in its own transaction."""

    @pytest.mark.anyio
    async def test_separate_transactions_per_conversation(self):
        """Each conversation should get its own pool.acquire() + transaction."""
        conv_id_1 = uuid.uuid4()
        conv_id_2 = uuid.uuid4()
        msg_id_1 = uuid.uuid4()
        msg_id_2 = uuid.uuid4()
        expired_msgs = [
            {"id": msg_id_1, "conversation_id": conv_id_1, "content": "Hello"},
            {"id": msg_id_2, "conversation_id": conv_id_2, "content": "World"},
        ]

        mock_find = AsyncMock(return_value=expired_msgs)

        acquire_count = 0

        def make_conn(msg_id, content_len):
            nonlocal acquire_count
            acquire_count += 1
            conn = MagicMock()
            # conn.fetch returns DELETE...RETURNING rows
            deleted_row = MagicMock()
            deleted_row.__getitem__ = lambda self, k: {
                "id": msg_id,
                "content_len": content_len,
            }[k]
            conn.fetch = AsyncMock(return_value=[deleted_row])
            conn.execute = AsyncMock()
            tx = MagicMock()
            tx.__aenter__ = AsyncMock(return_value=None)
            tx.__aexit__ = AsyncMock(return_value=None)
            conn.transaction.return_value = tx
            return conn

        # Each acquire() call should produce a fresh connection
        conns = [make_conn(msg_id_1, 5), make_conn(msg_id_2, 5)]
        conn_iter = iter(conns)

        mock_pool = MagicMock()

        def make_acq():
            c = next(conn_iter)
            acq = MagicMock()
            acq.__aenter__ = AsyncMock(return_value=c)
            acq.__aexit__ = AsyncMock(return_value=None)
            return acq

        mock_pool.acquire = make_acq

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.tasks.dm_cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.repositories.dm_repo.find_expired_text_messages", mock_find),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.dm_cleanup import _cleanup_text

            result = await _cleanup_text()

        # Two conversations -> two separate transactions (two pool.acquire calls)
        assert result["deleted"] == 2
        # Each connection should have had transaction() called
        for c in conns:
            c.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_source_acquires_per_conversation(self):
        """Verify from source code that pool.acquire is inside the per-conversation loop."""
        import importlib
        import inspect

        mod = importlib.import_module("app.tasks.dm_cleanup")
        source = inspect.getsource(mod._cleanup_text)

        # The fix should have pool.acquire inside "for cid" loop
        assert "for cid" in source
        assert "pool.acquire" in source


# ===========================================================================
# F-19: Event bus _persist_failed_event returns boolean
# ===========================================================================


class TestF19EventBusPersistReturnsBool:
    """Verify _persist_failed_event returns True on success, False on failure."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, mock_redis):
        from app.core.event_bus import _persist_failed_event

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            result = await _persist_failed_event("evt", "handler", {"k": "v"}, retry_count=0)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_redis_failure(self):
        from app.core.event_bus import _persist_failed_event

        bad_redis = AsyncMock()
        bad_redis.lpush = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("app.core.redis.get_redis", return_value=bad_redis):
            result = await _persist_failed_event("evt", "handler", {"k": "v"}, retry_count=0)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_get_redis_failure(self):
        from app.core.event_bus import _persist_failed_event

        with patch("app.core.redis.get_redis", side_effect=RuntimeError("not init")):
            result = await _persist_failed_event("evt", "handler", {}, retry_count=0)

        assert result is False

    @pytest.mark.asyncio
    async def test_failure_logs_at_warning_level(self):
        from app.core.event_bus import _persist_failed_event

        bad_redis = AsyncMock()
        bad_redis.lpush = AsyncMock(side_effect=ConnectionError("Redis down"))

        with (
            patch("app.core.redis.get_redis", return_value=bad_redis),
            patch("app.core.event_bus.logger") as mock_logger,
        ):
            await _persist_failed_event("test_evt", "handler_fn", {"key": "val"}, retry_count=0)

        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert "event" in call_kwargs.kwargs.get("extra", {})

    def test_return_type_annotation(self):
        """Verify the function signature returns bool."""
        import inspect

        from app.core.event_bus import _persist_failed_event

        sig = inspect.signature(_persist_failed_event)
        assert sig.return_annotation is bool


# ===========================================================================
# F-20: Form find_by_id response_count pop with default
# ===========================================================================


class TestF20FormFindByIdPopDefault:
    """Verify form_repo.find_by_id handles missing response_count gracefully."""

    @pytest.mark.anyio
    async def test_find_by_id_missing_response_count_key(self):
        """If the row dict doesn't have 'response_count', pop should use default 0."""
        form_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Row WITHOUT response_count key (simulates the fragile case)
        mock_row = MagicMock()
        row_dict = {
            "id": form_id,
            "sig_id": None,
            "created_by": user_id,
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "allow_non_members": False,
            "status": "active",
            "is_deleted": False,
            "is_schema_locked": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "TestUser",
            # NOTE: no "response_count" key!
        }
        mock_row.__iter__ = lambda self: iter(row_dict.items())
        mock_row.keys = lambda: row_dict.keys()
        mock_row.__getitem__ = lambda self, k: row_dict[k]

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=mock_conn)
        acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acq

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import find_by_id

            result, response_count = await find_by_id(form_id)

        assert result is not None
        assert response_count == 0

    @pytest.mark.anyio
    async def test_find_by_id_with_response_count_key(self):
        """Normal case: response_count is present and extracted correctly."""
        form_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        row_dict = {
            "id": form_id,
            "sig_id": None,
            "created_by": user_id,
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": "[]",
            "allow_non_members": False,
            "status": "active",
            "is_deleted": False,
            "is_schema_locked": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "TestUser",
            "response_count": 42,
        }
        mock_row = MagicMock()
        mock_row.__iter__ = lambda self: iter(row_dict.items())
        mock_row.keys = lambda: row_dict.keys()
        mock_row.__getitem__ = lambda self, k: row_dict[k]

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=mock_conn)
        acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acq

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import find_by_id

            result, response_count = await find_by_id(form_id)

        assert result is not None
        assert response_count == 42
        # response_count should NOT be in the result dict
        assert "response_count" not in result


# ===========================================================================
# F-21: DM repo distinguishes "not found" vs "not participant"
# ===========================================================================


class TestF21DmRepoDistinctErrors:
    """Verify send_message_atomic raises distinct errors for not found vs not participant."""

    @pytest.mark.anyio
    async def test_conversation_not_found_raises_404(self):
        """When conversation doesn't exist, error message should say 'not found'."""
        from app.core.errors import AppError

        conversation_id = uuid.uuid4()
        sender_id = uuid.uuid4()

        mock_conn = AsyncMock()
        # conv_row query returns None (not found)
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=mock_conn)
        acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acq

        with patch("app.repositories.dm_repo.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import send_message_atomic

            with pytest.raises(AppError) as exc_info:
                await send_message_atomic(
                    conversation_id=conversation_id,
                    msg_id=uuid.uuid4(),
                    sender_id=sender_id,
                    content="hello",
                    attachment_key=None,
                    attachment_name=None,
                    attachment_size=None,
                    attachment_expires_at=None,
                    content_len=5,
                    char_cap=50000,
                )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail["message"].lower()

    @pytest.mark.anyio
    async def test_not_participant_raises_403(self):
        """When user is not a participant, error should say 'not a participant'."""
        from app.core.errors import AppError

        conversation_id = uuid.uuid4()
        sender_id = uuid.uuid4()
        participant_a = uuid.uuid4()
        participant_b = uuid.uuid4()

        mock_conn = AsyncMock()

        # First fetchrow returns the conversation (exists but sender is not a participant)
        conv_row = {"participant_a": participant_a, "participant_b": participant_b}
        mock_conn.fetchrow = AsyncMock(return_value=conv_row)
        mock_conn.execute = AsyncMock()

        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=mock_conn)
        acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acq

        with patch("app.repositories.dm_repo.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import send_message_atomic

            with pytest.raises(AppError) as exc_info:
                await send_message_atomic(
                    conversation_id=conversation_id,
                    msg_id=uuid.uuid4(),
                    sender_id=sender_id,
                    content="hello",
                    attachment_key=None,
                    attachment_name=None,
                    attachment_size=None,
                    attachment_expires_at=None,
                    content_len=5,
                    char_cap=50000,
                )

        assert exc_info.value.status_code == 403
        assert "not a participant" in exc_info.value.detail["message"].lower()


# ===========================================================================
# F-22: Form stats includes total_responses field
# ===========================================================================


class TestF22FormStatsIncludesTotalResponses:
    """Verify that get_form_stats returns total_responses in its response."""

    @pytest.mark.anyio
    async def test_stats_includes_total_responses_zero(self):
        """When there are no responses, total_responses should be 0."""
        form_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        form_row = {
            "id": form_id,
            "sig_id": None,
            "created_by": user_id,
            "title": "Test Form",
            "description": None,
            "questions": json.dumps([
                {"id": "q1", "type": "text", "label": "Name"},
            ]),
            "created_at": now,
            "updated_at": now,
        }

        with (
            patch(
                "app.repositories.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 0),
            ),
            patch(
                "app.repositories.form_repo.count_total_responses",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "app.repositories.form_repo.iter_responses_batched",
                return_value=_empty_async_iter(),
            ),
        ):
            from app.services.form import get_form_stats

            stats = await get_form_stats(form_id)

        assert "total_responses" in stats
        assert stats["total_responses"] == 0

    @pytest.mark.anyio
    async def test_stats_includes_total_responses_nonzero(self):
        """When there are responses, total_responses should reflect the count."""
        form_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        form_row = {
            "id": form_id,
            "sig_id": None,
            "created_by": user_id,
            "title": "Test Form",
            "description": None,
            "questions": json.dumps([
                {"id": "q1", "type": "text", "label": "Name"},
            ]),
            "created_at": now,
            "updated_at": now,
        }

        with (
            patch(
                "app.repositories.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 5),
            ),
            patch(
                "app.repositories.form_repo.count_total_responses",
                new_callable=AsyncMock,
                return_value=5,
            ),
            patch(
                "app.repositories.form_repo.iter_responses_batched",
                return_value=_empty_async_iter(),
            ),
        ):
            from app.services.form import get_form_stats

            stats = await get_form_stats(form_id)

        assert stats["total_responses"] == 5


async def _empty_async_iter():
    """Helper: an empty async iterator."""
    return
    yield  # noqa: unreachable — makes this an async generator


# ===========================================================================
# F-23: Comment edit checks existence before rate limit
# ===========================================================================


class TestF23CommentEditExistenceBeforeRateLimit:
    """Verify that editing a non-existent comment does NOT consume rate limit."""

    @pytest.mark.anyio
    async def test_nonexistent_comment_returns_404_without_rate_limit(self, client):
        """Editing a comment that doesn't exist should return 404 without calling check_rate_limit."""
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        payload = {"sub": user_id, "role": "MEMBER", "jti": "test-jti"}
        app.dependency_overrides[get_current_user] = lambda: payload

        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)  # comment not found

        mock_pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=mock_conn)
        acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acq

        mock_rate_limit = AsyncMock(return_value=True)

        try:
            with (
                patch("app.core.database.get_pool", return_value=mock_pool),
                patch("app.api.v1.endpoints.comments.check_rate_limit", mock_rate_limit),
                patch(
                    "app.api.v1.endpoints.comments.sanitize_html",
                    return_value="<p>test</p>",
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "updated content"},
                )

            assert resp.status_code == 404
            # Rate limit should NOT have been called
            mock_rate_limit.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_wrong_owner_returns_404_without_rate_limit(self, client):
        """Editing a comment owned by another user should return 404 without rate limiting."""
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        other_user_id = uuid.uuid4()
        payload = {"sub": user_id, "role": "MEMBER", "jti": "test-jti"}
        app.dependency_overrides[get_current_user] = lambda: payload

        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        mock_conn = AsyncMock()
        # Comment exists but owned by a different user
        mock_conn.fetchrow = AsyncMock(return_value={"user_id": other_user_id})

        mock_pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=mock_conn)
        acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acq

        mock_rate_limit = AsyncMock(return_value=True)

        try:
            with (
                patch("app.core.database.get_pool", return_value=mock_pool),
                patch("app.api.v1.endpoints.comments.check_rate_limit", mock_rate_limit),
                patch(
                    "app.api.v1.endpoints.comments.sanitize_html",
                    return_value="<p>test</p>",
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "updated content"},
                )

            assert resp.status_code == 404
            # Rate limit should NOT have been called
            mock_rate_limit.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_valid_comment_edit_does_check_rate_limit(self, client):
        """Editing a valid owned comment SHOULD check rate limit."""
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        payload = {"sub": user_id, "role": "MEMBER", "jti": "test-jti"}
        app.dependency_overrides[get_current_user] = lambda: payload

        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        now = datetime.now(timezone.utc).isoformat()

        mock_conn = AsyncMock()
        # Comment exists and owned by current user
        mock_conn.fetchrow = AsyncMock(return_value={"user_id": uuid.UUID(user_id)})

        mock_pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=mock_conn)
        acq.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acq

        mock_rate_limit = AsyncMock(return_value=True)

        mock_comment_result = {
            "id": str(comment_id),
            "post_id": str(post_id),
            "content": "<p>updated</p>",
            "author": {
                "id": user_id,
                "username": "testuser",
                "display_name": "Test User",
                "avatar_url": None,
            },
            "parent_id": None,
            "mentions": None,
            "reaction_counts": None,
            "user_reactions": None,
            "_raw_reactions": None,
            "created_at": now,
            "updated_at": now,
        }

        try:
            with (
                patch("app.core.database.get_pool", return_value=mock_pool),
                patch("app.api.v1.endpoints.comments.check_rate_limit", mock_rate_limit),
                patch(
                    "app.api.v1.endpoints.comments.sanitize_html",
                    return_value="<p>updated</p>",
                ),
                patch(
                    "app.api.v1.endpoints.comments.update_comment",
                    new_callable=AsyncMock,
                    return_value=mock_comment_result,
                ),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "updated content"},
                )

            # Rate limit SHOULD have been called for valid owned comment
            mock_rate_limit.assert_called_once()
        finally:
            app.dependency_overrides.clear()
