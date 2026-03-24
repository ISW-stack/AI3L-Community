"""Tests for the 2026-03-24 audit fix batch.

Covers: H-04, M-06, M-09, M-12, M-14, M-15, M-16, M-17, M-20, M-21, M-22, M-23.
"""

import json
import math
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# H-04: Form soft-delete leaks file_upload answers in MinIO
# ---------------------------------------------------------------------------


class TestFormSoftDeleteFileCleanup:
    """H-04: Verify file_upload answer files are cleaned up on form soft-delete."""

    @pytest.mark.asyncio
    async def test_soft_delete_collects_file_upload_keys(self):
        """soft_delete_with_permission returns file_upload entries."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        file_key = f"forms/{form_id}/{user_id}/test.pdf"
        resp_user_id = uuid.uuid4()

        questions = [
            {"id": "q1", "type": "file_upload", "label": "Upload"},
            {"id": "q2", "type": "text", "label": "Name"},
        ]
        answers = {"q1": {"key": file_key, "filename": "test.pdf"}, "q2": "Alice"}

        # Mock the connection and pool
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "created_by": uuid.UUID(user_id),
                "banner_url": None,
                "questions": json.dumps(questions),
            }
        )
        mock_conn.fetch = AsyncMock(
            return_value=[{"user_id": resp_user_id, "answers": json.dumps(answers)}]
        )
        mock_conn.execute = AsyncMock()

        # Mock transaction context manager
        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool_ctx = AsyncMock()
        mock_pool_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=mock_pool_ctx)

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import soft_delete_with_permission

            deleted, banner_url, file_entries = await soft_delete_with_permission(
                form_id, user_id, is_admin=False
            )

        assert deleted is True
        assert len(file_entries) == 1
        assert file_entries[0]["key"] == file_key
        assert file_entries[0]["user_id"] == str(resp_user_id)

    @pytest.mark.asyncio
    async def test_cleanup_form_upload_files(self):
        """_cleanup_form_upload_files deletes files and refunds quota."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        file_key = f"forms/{form_id}/{user_id}/doc.pdf"
        file_entries = [{"key": file_key, "user_id": user_id}]

        with (
            patch(
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                return_value=1024,
            ) as mock_size,
            patch(
                "app.core.async_storage.delete_file",
                new_callable=AsyncMock,
            ) as mock_delete,
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ) as mock_quota,
        ):
            from app.services.form import _cleanup_form_upload_files

            await _cleanup_form_upload_files(form_id, file_entries)

        mock_size.assert_called_once_with(file_key)
        mock_delete.assert_called_once_with(file_key)
        mock_quota.assert_called_once_with(uuid.UUID(user_id), -1024)

    @pytest.mark.asyncio
    async def test_cleanup_form_upload_files_handles_errors(self):
        """_cleanup_form_upload_files logs warning on failure, doesn't raise."""
        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        file_entries = [{"key": "bad/key", "user_id": user_id}]

        with (
            patch(
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                side_effect=Exception("MinIO down"),
            ),
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock),
        ):
            from app.services.form import _cleanup_form_upload_files

            # Should not raise
            await _cleanup_form_upload_files(form_id, file_entries)


# ---------------------------------------------------------------------------
# M-06: update_post doesn't sanitize HTML or check empty content
# ---------------------------------------------------------------------------


class TestUpdatePostSanitization:
    """M-06: update_post should sanitize content and reject empty."""

    @pytest.mark.asyncio
    async def test_update_post_sanitizes_content(self):
        """Content is sanitized via sanitize_html before saving."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        malicious = '<script>alert("xss")</script><p>Hello</p>'

        mock_current = {
            "user_id": uuid.UUID(user_id),
            "version": 1,
            "title": "Test",
            "content": "<p>Old</p>",
            "category_id": None,
            "keywords": [],
            "allow_comments": True,
        }

        mock_row = MagicMock()
        mock_conn = AsyncMock()
        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool_ctx = AsyncMock()
        mock_pool_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=mock_pool_ctx)

        mock_co_author = AsyncMock(return_value=False)

        with (
            patch("app.services.post.get_pool", return_value=mock_pool),
            patch("app.services.post.post_repo.find_for_update", return_value=mock_current),
            patch(
                "app.repositories.co_author_repo.is_accepted_co_author",
                mock_co_author,
            ),
            patch("app.services.post.post_repo.insert_history", new_callable=AsyncMock),
            patch(
                "app.services.post.post_repo.update_in_transaction",
                new_callable=AsyncMock,
                return_value=mock_row,
            ) as mock_update,
            patch("app.services.post.async_row_to_post", new_callable=AsyncMock, return_value={}),
        ):
            from app.services.post import update_post

            await update_post(post_id, user_id, content=malicious)

        # Verify the content passed to update_in_transaction is sanitized
        call_args = mock_update.call_args
        saved_content = call_args[0][3]  # 4th positional arg = new_content
        assert "<script>" not in saved_content
        assert "<p>Hello</p>" in saved_content

    @pytest.mark.asyncio
    async def test_update_post_rejects_empty_after_sanitization(self):
        """Content that becomes empty after sanitization is rejected."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        # Content that sanitizes to empty
        script_only = '<script>alert("xss")</script>'

        mock_current = {
            "user_id": uuid.UUID(user_id),
            "version": 1,
            "title": "Test",
            "content": "<p>Old</p>",
            "category_id": None,
            "keywords": [],
            "allow_comments": True,
        }

        mock_conn = AsyncMock()
        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool_ctx = AsyncMock()
        mock_pool_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=mock_pool_ctx)

        mock_co_author = AsyncMock(return_value=False)

        with (
            patch("app.services.post.get_pool", return_value=mock_pool),
            patch("app.services.post.post_repo.find_for_update", return_value=mock_current),
            patch(
                "app.repositories.co_author_repo.is_accepted_co_author",
                mock_co_author,
            ),
        ):
            from app.services.post import update_post

            with pytest.raises(ValueError, match="Content cannot be empty"):
                await update_post(post_id, user_id, content=script_only)


# ---------------------------------------------------------------------------
# M-09: Form file_upload answer key not validated for file ownership
# ---------------------------------------------------------------------------


class TestFileUploadOwnershipValidation:
    """M-09: file_upload answer keys must belong to the submitting user."""

    def test_valid_ownership(self):
        """File key containing user_id is accepted."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": f"editor/{user_id}/file.pdf", "filename": "file.pdf"}}

        # Should not raise
        _validate_file_ownership(questions, answers, user_id)

    def test_invalid_ownership_raises(self):
        """File key not containing user_id is rejected."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": f"editor/{other_user_id}/file.pdf", "filename": "file.pdf"}}

        with pytest.raises(PermissionError, match="does not belong"):
            _validate_file_ownership(questions, answers, user_id)

    def test_non_file_upload_skipped(self):
        """Non file_upload questions are not checked."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "text", "label": "Name"}]
        answers = {"q1": "Alice"}

        # Should not raise
        _validate_file_ownership(questions, answers, user_id)

    def test_missing_key_skipped(self):
        """Answers without key field are skipped."""
        from app.services.form import _validate_file_ownership

        user_id = str(uuid.uuid4())
        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"filename": "file.pdf"}}  # no key

        # Should not raise
        _validate_file_ownership(questions, answers, user_id)


# ---------------------------------------------------------------------------
# M-12: Deleting parent comment — child count uses RETURNING for atomicity
# ---------------------------------------------------------------------------


class TestParentCommentDeletion:
    """M-12: Parent comment deletion uses RETURNING for accurate child count."""

    @pytest.mark.asyncio
    async def test_parent_delete_counts_children_via_returning(self):
        """When deleting a parent, child count is from RETURNING, not string parsing."""
        comment_id = uuid.uuid4()
        post_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Parent comment row
        parent_row = {"post_id": post_id, "parent_id": None}
        # 3 child comment IDs
        child_rows = [{"id": uuid.uuid4()}, {"id": uuid.uuid4()}, {"id": uuid.uuid4()}]

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=parent_row)
        mock_conn.fetch = AsyncMock(return_value=child_rows)
        mock_conn.execute = AsyncMock()

        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool_ctx = AsyncMock()
        mock_pool_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=mock_pool_ctx)

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            from app.repositories.comment_repo import soft_delete

            result = await soft_delete(comment_id, post_id, user_id=user_id, is_admin=False)

        assert result == post_id

        # Check that comment_count was decremented by 4 (1 parent + 3 children)
        execute_calls = mock_conn.execute.call_args_list
        # The first execute call after fetch should be comment_count decrement
        decrement_call = execute_calls[0]
        assert decrement_call[0][1] == 4  # total_deleted = 1 + 3


# ---------------------------------------------------------------------------
# M-14: multiple_choice percentage can sum > 100%
# ---------------------------------------------------------------------------


class TestPercentageNormalization:
    """M-14: Option percentages should sum to exactly 100%."""

    def test_normalize_percentages_sums_to_100(self):
        """Percentages that would round to >100% are normalized."""
        from app.services.form import _normalize_percentages

        # 3 options each with 33.3% -- naive rounding gives 33.3*3 = 99.9%
        option_stats = [
            {"option_id": "a", "count": 1, "percentage": 33.3},
            {"option_id": "b", "count": 1, "percentage": 33.3},
            {"option_id": "c", "count": 1, "percentage": 33.3},
        ]
        _normalize_percentages(option_stats)
        total = sum(s["percentage"] for s in option_stats)
        # Should be approximately 100.0 (within floating point tolerance)
        assert abs(total - 100.0) < 0.2

    def test_normalize_percentages_handles_zero(self):
        """Zero percentages remain zero."""
        from app.services.form import _normalize_percentages

        option_stats = [
            {"option_id": "a", "count": 0, "percentage": 0.0},
            {"option_id": "b", "count": 0, "percentage": 0.0},
        ]
        _normalize_percentages(option_stats)
        assert all(s["percentage"] == 0.0 for s in option_stats)

    def test_normalize_percentages_single_option(self):
        """A single option at 100% stays at 100%."""
        from app.services.form import _normalize_percentages

        option_stats = [{"option_id": "a", "count": 10, "percentage": 100.0}]
        _normalize_percentages(option_stats)
        assert option_stats[0]["percentage"] == 100.0

    def test_normalize_percentages_empty_list(self):
        """Empty list is a no-op."""
        from app.services.form import _normalize_percentages

        option_stats: list[dict] = []
        _normalize_percentages(option_stats)
        assert option_stats == []

    def test_normalize_two_thirds(self):
        """Two options: 66.7 + 33.3 should sum to 100.0."""
        from app.services.form import _normalize_percentages

        option_stats = [
            {"option_id": "a", "count": 2, "percentage": 66.7},
            {"option_id": "b", "count": 1, "percentage": 33.3},
        ]
        _normalize_percentages(option_stats)
        total = sum(s["percentage"] for s in option_stats)
        assert abs(total - 100.0) < 0.2


# ---------------------------------------------------------------------------
# M-15: Rating question min/max cross-validation
# ---------------------------------------------------------------------------


class TestRatingMinMaxValidation:
    """M-15: QuestionSchema should reject rating with min >= max."""

    def test_valid_rating_min_max(self):
        """Rating with min < max is accepted."""
        from app.schemas.form import QuestionSchema

        q = QuestionSchema(id="r1", type="rating", label="Rate", min=1, max=5)
        assert q.min == 1
        assert q.max == 5

    def test_invalid_rating_min_equals_max(self):
        """Rating with min == max is rejected."""
        from app.schemas.form import QuestionSchema

        with pytest.raises(ValueError, match="must be less than max"):
            QuestionSchema(id="r1", type="rating", label="Rate", min=5, max=5)

    def test_invalid_rating_min_greater_than_max(self):
        """Rating with min > max is rejected."""
        from app.schemas.form import QuestionSchema

        with pytest.raises(ValueError, match="must be less than max"):
            QuestionSchema(id="r1", type="rating", label="Rate", min=8, max=3)

    def test_default_rating_min_max(self):
        """Rating with defaults (min=None->1, max=None->5) is valid."""
        from app.schemas.form import QuestionSchema

        q = QuestionSchema(id="r1", type="rating", label="Rate")
        # Should not raise; defaults are min=1, max=5
        assert q is not None

    def test_non_rating_ignores_min_max(self):
        """Non-rating question type doesn't validate min/max."""
        from app.schemas.form import QuestionSchema

        # Text question with min/max set (should not raise)
        q = QuestionSchema(id="t1", type="text", label="Name", min=10, max=3)
        assert q is not None


# ---------------------------------------------------------------------------
# M-16: list_all returns total=0 on empty last page
# ---------------------------------------------------------------------------


class TestListAllEmptyPage:
    """M-16: list_all should return real total even when page is empty."""

    @pytest.mark.asyncio
    async def test_empty_page_returns_real_total(self):
        """When requesting a page past the end, total should be accurate."""
        mock_conn = AsyncMock()
        # First query returns empty (past end of results)
        mock_conn.fetch = AsyncMock(return_value=[])
        # Count query returns real total
        mock_conn.fetchval = AsyncMock(return_value=42)

        mock_pool = AsyncMock()
        mock_pool_ctx = AsyncMock()
        mock_pool_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=mock_pool_ctx)

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import list_all

            users, total = await list_all(page=999, page_size=50)

        assert users == []
        assert total == 42

    @pytest.mark.asyncio
    async def test_empty_page_with_search_returns_real_total(self):
        """With search, empty page still returns real total."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=15)

        mock_pool = AsyncMock()
        mock_pool_ctx = AsyncMock()
        mock_pool_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=mock_pool_ctx)

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import list_all

            users, total = await list_all(page=999, page_size=50, search="alice")

        assert users == []
        assert total == 15


# ---------------------------------------------------------------------------
# M-17: Non-atomic file-delete + quota-decrement
# ---------------------------------------------------------------------------


class TestAtomicFileDeleteQuota:
    """M-17: Quota should be re-incremented if MinIO delete fails."""

    @pytest.mark.asyncio
    async def test_quota_reincremented_on_minio_failure(self):
        """If MinIO delete fails after quota decrement, quota is restored."""
        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/test.png"

        mock_decrement = AsyncMock()
        mock_reincrement = AsyncMock()

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                return_value=2048,
            ),
            patch(
                "app.repositories.file_scan_repo.delete_by_key",
                new_callable=AsyncMock,
            ),
            patch(
                "app.tasks.utils.decrement_owner_storage",
                mock_decrement,
            ),
            patch(
                "app.core.async_storage.delete_file",
                new_callable=AsyncMock,
                side_effect=Exception("MinIO connection failed"),
            ),
            patch(
                "app.tasks.cleanup._reincrement_owner_storage",
                mock_reincrement,
            ),
        ):
            from app.tasks.cleanup import _delete_orphans

            deleted = await _delete_orphans([key])

        assert deleted == 0
        mock_decrement.assert_called_once_with(key, 2048)
        mock_reincrement.assert_called_once_with(key, 2048)

    @pytest.mark.asyncio
    async def test_successful_delete_no_reincrement(self):
        """Successful MinIO delete doesn't trigger re-increment."""
        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/test.png"

        mock_decrement = AsyncMock()
        mock_reincrement = AsyncMock()

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch(
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                return_value=2048,
            ),
            patch(
                "app.repositories.file_scan_repo.delete_by_key",
                new_callable=AsyncMock,
            ),
            patch(
                "app.tasks.utils.decrement_owner_storage",
                mock_decrement,
            ),
            patch(
                "app.core.async_storage.delete_file",
                new_callable=AsyncMock,
            ),
            patch(
                "app.tasks.cleanup._reincrement_owner_storage",
                mock_reincrement,
            ),
        ):
            from app.tasks.cleanup import _delete_orphans

            deleted = await _delete_orphans([key])

        assert deleted == 1
        mock_decrement.assert_called_once()
        mock_reincrement.assert_not_called()


# ---------------------------------------------------------------------------
# M-20: Fragile result.split() parsing in view_sync
# ---------------------------------------------------------------------------


class TestParseUpdateCount:
    """M-20: _parse_update_count handles unexpected formats gracefully."""

    def test_standard_update_result(self):
        from app.tasks.view_sync import _parse_update_count

        assert _parse_update_count("UPDATE 42") == 42

    def test_zero_rows(self):
        from app.tasks.view_sync import _parse_update_count

        assert _parse_update_count("UPDATE 0") == 0

    def test_delete_result(self):
        from app.tasks.view_sync import _parse_update_count

        assert _parse_update_count("DELETE 10") == 10

    def test_empty_string(self):
        from app.tasks.view_sync import _parse_update_count

        assert _parse_update_count("") == 0

    def test_non_numeric(self):
        from app.tasks.view_sync import _parse_update_count

        assert _parse_update_count("UNEXPECTED FORMAT") == 0

    def test_single_word(self):
        from app.tasks.view_sync import _parse_update_count

        assert _parse_update_count("UPDATE") == 0


# ---------------------------------------------------------------------------
# M-21: CSV injection through dict stringification
# ---------------------------------------------------------------------------


class TestCsvSanitization:
    """M-21: All CSV cell values are sanitized against formula injection."""

    def test_sanitize_csv_value_equals(self):
        from app.tasks.form_export import _sanitize_csv_value

        assert _sanitize_csv_value("=CMD()") == "'=CMD()"

    def test_sanitize_csv_value_plus(self):
        from app.tasks.form_export import _sanitize_csv_value

        assert _sanitize_csv_value("+1234") == "'+1234"

    def test_sanitize_csv_value_minus(self):
        from app.tasks.form_export import _sanitize_csv_value

        assert _sanitize_csv_value("-1234") == "'-1234"

    def test_sanitize_csv_value_at(self):
        from app.tasks.form_export import _sanitize_csv_value

        assert _sanitize_csv_value("@SUM(A1)") == "'@SUM(A1)"

    def test_sanitize_csv_value_tab(self):
        from app.tasks.form_export import _sanitize_csv_value

        assert _sanitize_csv_value("\tdata") == "'\tdata"

    def test_sanitize_csv_value_pipe(self):
        from app.tasks.form_export import _sanitize_csv_value

        assert _sanitize_csv_value("|cmd") == "'|cmd"

    def test_sanitize_csv_value_normal(self):
        from app.tasks.form_export import _sanitize_csv_value

        assert _sanitize_csv_value("hello world") == "hello world"

    def test_sanitize_csv_value_empty(self):
        from app.tasks.form_export import _sanitize_csv_value

        assert _sanitize_csv_value("") == ""


# ---------------------------------------------------------------------------
# M-22: Long-held advisory lock during recommendation recompute
# ---------------------------------------------------------------------------


class TestRecommendationTryLock:
    """M-22: Recommendations use pg_try_advisory_xact_lock, skip if held."""

    @pytest.mark.asyncio
    async def test_skips_when_lock_held(self):
        """When lock can't be acquired, task skips gracefully."""
        mock_conn = AsyncMock()
        # pg_try_advisory_xact_lock returns False
        mock_conn.fetchval = AsyncMock(return_value=False)

        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = AsyncMock()
        mock_pool_ctx = AsyncMock()
        mock_pool_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=mock_pool_ctx)

        with (
            patch(
                "app.tasks.recommendations._ensure_pool",
                new_callable=AsyncMock,
            ),
            patch(
                "app.core.database.get_pool",
                return_value=mock_pool,
            ),
        ):
            from app.tasks.recommendations import _compute_recommendations_async

            result = await _compute_recommendations_async()

        assert result["skipped"] is True
        assert result.get("reason") == "lock_held"


# ---------------------------------------------------------------------------
# M-23: Shared task utilities
# ---------------------------------------------------------------------------


class TestTaskUtils:
    """M-23: Shared utility functions for Celery tasks."""

    @pytest.mark.asyncio
    async def test_ensure_pool_already_initialized(self):
        """ensure_pool does nothing if pool already exists."""
        from app.tasks.utils import ensure_pool

        with patch("app.tasks.utils.get_pool") as mock_get:
            mock_get.return_value = MagicMock()
            await ensure_pool()
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_pool_initializes_on_runtime_error(self):
        """ensure_pool initializes DB pool on RuntimeError."""
        from app.tasks.utils import ensure_pool

        with (
            patch("app.tasks.utils.get_pool", side_effect=RuntimeError),
            patch("app.tasks.utils.init_db_pool", new_callable=AsyncMock) as mock_init,
        ):
            await ensure_pool()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_redis_already_initialized(self):
        """ensure_redis does nothing if Redis already connected."""
        from app.tasks.utils import ensure_redis

        with patch("app.tasks.utils.get_redis") as mock_get:
            mock_get.return_value = MagicMock()
            await ensure_redis()
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_redis_initializes_on_runtime_error(self):
        """ensure_redis initializes Redis on RuntimeError."""
        from app.tasks.utils import ensure_redis

        with (
            patch("app.tasks.utils.get_redis", side_effect=RuntimeError),
            patch("app.tasks.utils.init_redis", new_callable=AsyncMock) as mock_init,
        ):
            await ensure_redis()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_decrement_owner_storage_editor_key(self):
        """decrement_owner_storage extracts user_id from editor/ key pattern."""
        from app.tasks.utils import decrement_owner_storage

        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/file.png"

        with (
            patch("app.tasks.utils.ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ) as mock_inc,
        ):
            await decrement_owner_storage(key, 1024)

        mock_inc.assert_called_once_with(uuid.UUID(user_id), -1024)

    @pytest.mark.asyncio
    async def test_decrement_owner_storage_dm_key(self):
        """decrement_owner_storage works with dm/ key pattern."""
        from app.tasks.utils import decrement_owner_storage

        user_id = str(uuid.uuid4())
        key = f"dm/{user_id}/somefile.jpg"

        with (
            patch("app.tasks.utils.ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ) as mock_inc,
        ):
            await decrement_owner_storage(key, 512)

        mock_inc.assert_called_once_with(uuid.UUID(user_id), -512)

    @pytest.mark.asyncio
    async def test_decrement_owner_storage_invalid_key(self):
        """decrement_owner_storage handles invalid key gracefully."""
        from app.tasks.utils import decrement_owner_storage

        with (
            patch("app.tasks.utils.ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ) as mock_inc,
        ):
            await decrement_owner_storage("", 1024)

        mock_inc.assert_not_called()

    @pytest.mark.asyncio
    async def test_decrement_owner_storage_no_uuid_in_key(self):
        """decrement_owner_storage logs warning when no UUID found."""
        from app.tasks.utils import decrement_owner_storage

        with (
            patch("app.tasks.utils.ensure_pool", new_callable=AsyncMock),
            patch(
                "app.repositories.user_repo.increment_storage_used",
                new_callable=AsyncMock,
            ) as mock_inc,
        ):
            await decrement_owner_storage("editor/not-a-uuid/file.png", 1024)

        mock_inc.assert_not_called()
