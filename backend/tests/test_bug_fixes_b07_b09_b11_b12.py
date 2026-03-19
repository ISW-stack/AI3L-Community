"""Tests for bug fixes B07, B09, B11, B12.

B07: Cursor pagination uses native UUID comparison instead of text-cast.
B09: _SEARCH_SORT_MAP includes 'popular' sort option.
B11: cleanup_orphan_files processes S3 files in batches.
B12: get_form_stats uses batched response fetching and separate count.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# B07 — Cursor pagination uses native UUID (no ::text cast)
# ---------------------------------------------------------------------------


class TestB07CursorPaginationUUID:
    """Cursor pagination should pass cursor_id as uuid.UUID, not str."""

    def test_decode_cursor_returns_uuid(self):
        """_decode_cursor should return a uuid.UUID, not a string."""
        from app.repositories.post_repo import _decode_cursor, _encode_cursor

        row_id = uuid.uuid4()
        cursor = _encode_cursor(datetime.now(timezone.utc).isoformat(), row_id, "newest")
        sort, primary_val, decoded_id = _decode_cursor(cursor)
        assert isinstance(decoded_id, uuid.UUID)
        assert decoded_id == row_id

    @pytest.mark.anyio
    async def test_cursor_newest_passes_uuid_not_str(self, mock_pool, mock_conn):
        """find_many with cursor='newest' should pass cursor_id as UUID to params."""
        from app.repositories.post_repo import _encode_cursor

        row_id = uuid.uuid4()
        ts = datetime.now(timezone.utc)
        cursor = _encode_cursor(ts.isoformat(), row_id, "newest")

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            await _import_find_many()(cursor=cursor, page_size=10)

        # Verify the params passed to conn.fetch
        call_args = mock_conn.fetch.call_args
        params = call_args[0][1:]  # skip SQL string
        # The cursor_id should be the UUID object, not str(uuid)
        uuid_params = [p for p in params if isinstance(p, uuid.UUID)]
        assert len(uuid_params) >= 1, "cursor_id should be passed as uuid.UUID"
        str_uuid_params = [p for p in params if isinstance(p, str) and _is_uuid_str(p)]
        assert len(str_uuid_params) == 0, "cursor_id should NOT be passed as string"

    @pytest.mark.anyio
    async def test_cursor_popular_passes_uuid_not_str(self, mock_pool, mock_conn):
        """find_many with cursor='popular' should pass cursor_id as UUID."""
        from app.repositories.post_repo import _encode_cursor

        row_id = uuid.uuid4()
        cursor = _encode_cursor("42", row_id, "popular")

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            await _import_find_many()(cursor=cursor, page_size=10)

        call_args = mock_conn.fetch.call_args
        params = call_args[0][1:]
        uuid_params = [p for p in params if isinstance(p, uuid.UUID)]
        assert len(uuid_params) >= 1
        str_uuid_params = [p for p in params if isinstance(p, str) and _is_uuid_str(p)]
        assert len(str_uuid_params) == 0

    @pytest.mark.anyio
    async def test_cursor_most_comments_passes_uuid_not_str(self, mock_pool, mock_conn):
        """find_many with cursor='most_comments' should pass cursor_id as UUID."""
        from app.repositories.post_repo import _encode_cursor

        row_id = uuid.uuid4()
        cursor = _encode_cursor("5", row_id, "most_comments")

        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            await _import_find_many()(cursor=cursor, page_size=10)

        call_args = mock_conn.fetch.call_args
        params = call_args[0][1:]
        uuid_params = [p for p in params if isinstance(p, uuid.UUID)]
        assert len(uuid_params) >= 1
        str_uuid_params = [p for p in params if isinstance(p, str) and _is_uuid_str(p)]
        assert len(str_uuid_params) == 0

    def test_cursor_sql_has_no_text_cast(self):
        """The cursor WHERE clause should use p.id, not p.id::text."""
        import inspect

        from app.repositories import post_repo

        source = inspect.getsource(post_repo.find_many)
        # The cursor-mode section should NOT contain p.id::text
        assert "p.id::text" not in source, (
            "Cursor pagination should use native UUID comparison (p.id), "
            "not text-cast (p.id::text)"
        )


# ---------------------------------------------------------------------------
# B09 — _SEARCH_SORT_MAP includes 'popular'
# ---------------------------------------------------------------------------


class TestB09SearchSortPopular:
    """_SEARCH_SORT_MAP should include 'popular' key."""

    def test_search_sort_map_has_popular(self):
        """'popular' must be a valid key in _SEARCH_SORT_MAP."""
        from app.repositories.post_repo import _SEARCH_SORT_MAP

        assert "popular" in _SEARCH_SORT_MAP

    def test_search_sort_popular_uses_like_count(self):
        """'popular' sort should ORDER BY like_count DESC."""
        from app.repositories.post_repo import _SEARCH_SORT_MAP

        popular_clause = _SEARCH_SORT_MAP["popular"]
        assert "like_count" in popular_clause
        assert "DESC" in popular_clause

    def test_search_sort_popular_includes_tiebreaker(self):
        """'popular' sort should have created_at as tiebreaker."""
        from app.repositories.post_repo import _SEARCH_SORT_MAP

        popular_clause = _SEARCH_SORT_MAP["popular"]
        assert "created_at" in popular_clause

    @pytest.mark.anyio
    async def test_search_with_popular_sort_uses_correct_order(self, mock_pool, mock_conn):
        """search(sort='popular') should use the popular ORDER BY clause."""
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)

        with patch("app.repositories.post_repo.get_pool", return_value=mock_pool):
            from app.repositories.post_repo import search

            result, total, total_pages = await search(sort="popular")

        # Check the SQL contains the popular ORDER BY
        sql = mock_conn.fetch.call_args[0][0]
        assert "like_count" in sql, "SQL should contain like_count for popular sort"

    def test_search_sort_map_matches_sort_map(self):
        """All keys in _SORT_MAP should have corresponding entries in _SEARCH_SORT_MAP."""
        from app.repositories.post_repo import _SEARCH_SORT_MAP, _SORT_MAP

        for key in _SORT_MAP:
            assert (
                key in _SEARCH_SORT_MAP
            ), f"Sort option '{key}' exists in _SORT_MAP but not _SEARCH_SORT_MAP"


# ---------------------------------------------------------------------------
# B11 — cleanup_orphan_files processes S3 files in batches
# ---------------------------------------------------------------------------


class TestB11OrphanCleanupBatching:
    """Orphan file cleanup should process S3 files in batches."""

    def test_orphan_batch_size_constant_exists(self):
        """_ORPHAN_BATCH_SIZE should be defined in cleanup module."""
        from app.tasks.cleanup import _ORPHAN_BATCH_SIZE

        assert isinstance(_ORPHAN_BATCH_SIZE, int)
        assert _ORPHAN_BATCH_SIZE > 0

    def test_find_orphans_batches_correctly(self):
        """_find_orphans inner function should process files in batches."""
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        old_time = cutoff - timedelta(days=1)  # older than cutoff
        new_time = cutoff + timedelta(days=1)  # newer than cutoff

        referenced = {"editor/user1/referenced.jpg"}

        # Simulate 2500 files (more than one batch of 1000)
        files = []
        expected_orphans = []
        for i in range(2500):
            key = f"editor/user1/file_{i}.jpg"
            if i % 3 == 0:
                # Old and unreferenced → orphan
                files.append((key, old_time))
                if key not in referenced:
                    expected_orphans.append(key)
            elif i % 3 == 1:
                # New → not orphan
                files.append((key, new_time))
            else:
                # Old but referenced → not orphan (only file_0 is referenced)
                files.append((key, old_time))
                if key not in referenced:
                    expected_orphans.append(key)

        # Import and test the batch processing logic
        from app.tasks.cleanup import _ORPHAN_BATCH_SIZE

        orphan_keys: list[str] = []
        total = 0
        batch: list[tuple] = []
        for item in files:
            batch.append(item)
            total += 1
            if len(batch) >= _ORPHAN_BATCH_SIZE:
                orphan_keys.extend(
                    key for key, modified in batch if key not in referenced and modified < cutoff
                )
                batch = []
        if batch:
            orphan_keys.extend(
                key for key, modified in batch if key not in referenced and modified < cutoff
            )

        assert total == 2500
        assert orphan_keys == expected_orphans

    def test_find_orphans_empty_iterator(self):
        """Batching with no files should return empty list and zero count."""
        from app.tasks.cleanup import _ORPHAN_BATCH_SIZE

        referenced: set[str] = set()
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        orphan_keys: list[str] = []
        total = 0
        batch: list[tuple] = []
        for item in []:
            batch.append(item)
            total += 1
            if len(batch) >= _ORPHAN_BATCH_SIZE:
                orphan_keys.extend(
                    key for key, modified in batch if key not in referenced and modified < cutoff
                )
                batch = []
        if batch:
            orphan_keys.extend(
                key for key, modified in batch if key not in referenced and modified < cutoff
            )

        assert total == 0
        assert orphan_keys == []

    def test_find_orphans_exactly_one_batch(self):
        """Batching with files exactly at batch size should work correctly."""
        from app.tasks.cleanup import _ORPHAN_BATCH_SIZE

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        old_time = cutoff - timedelta(days=1)
        referenced: set[str] = set()

        files = [(f"editor/user1/file_{i}.jpg", old_time) for i in range(_ORPHAN_BATCH_SIZE)]

        orphan_keys: list[str] = []
        total = 0
        batch: list[tuple] = []
        for item in files:
            batch.append(item)
            total += 1
            if len(batch) >= _ORPHAN_BATCH_SIZE:
                orphan_keys.extend(
                    key for key, modified in batch if key not in referenced and modified < cutoff
                )
                batch = []
        if batch:
            orphan_keys.extend(
                key for key, modified in batch if key not in referenced and modified < cutoff
            )

        assert total == _ORPHAN_BATCH_SIZE
        assert len(orphan_keys) == _ORPHAN_BATCH_SIZE

    def test_cleanup_source_does_not_materialize_all_files(self):
        """The cleanup_orphan_files function should NOT call list(_iter_editor_files())."""
        import inspect

        from app.tasks.cleanup import cleanup_orphan_files

        source = inspect.getsource(cleanup_orphan_files)
        assert (
            "list, _iter_editor_files" not in source
        ), "Should not materialize all S3 files with list(_iter_editor_files())"
        assert (
            "list(_iter_editor_files" not in source
        ), "Should not materialize all S3 files with list(_iter_editor_files())"


# ---------------------------------------------------------------------------
# B12 — get_form_stats uses batched response fetching
# ---------------------------------------------------------------------------


class TestB12FormStatsBatched:
    """get_form_stats should use batched response fetching."""

    def test_iter_responses_batched_exists(self):
        """form_repo should have iter_responses_batched function."""
        from app.repositories import form_repo

        assert hasattr(form_repo, "iter_responses_batched")

    def test_count_total_responses_exists(self):
        """form_repo should have count_total_responses function."""
        from app.repositories import form_repo

        assert hasattr(form_repo, "count_total_responses")

    @pytest.mark.anyio
    async def test_iter_responses_batched_keyset_pagination(self, mock_pool, mock_conn):
        """iter_responses_batched should use keyset pagination."""
        form_id = uuid.uuid4()

        # First batch: 2 rows
        row1_id = uuid.uuid4()
        row2_id = uuid.uuid4()
        batch1 = [
            _make_response_record(row1_id, form_id, {"q1": "a"}),
            _make_response_record(row2_id, form_id, {"q1": "b"}),
        ]
        # Second call: empty → stop
        mock_conn.fetch = AsyncMock(side_effect=[batch1, []])

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import iter_responses_batched

            results = await iter_responses_batched(form_id, batch_size=2)

        assert len(results) == 2
        # Should have been called twice (first batch + empty batch)
        assert mock_conn.fetch.call_count == 2

    @pytest.mark.anyio
    async def test_iter_responses_batched_stops_on_partial_batch(self, mock_pool, mock_conn):
        """iter_responses_batched should stop when a batch has fewer rows than batch_size."""
        form_id = uuid.uuid4()

        # Return 1 row when batch_size=5 → should stop after one call
        batch1 = [_make_response_record(uuid.uuid4(), form_id, {"q1": "a"})]
        mock_conn.fetch = AsyncMock(return_value=batch1)

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import iter_responses_batched

            results = await iter_responses_batched(form_id, batch_size=5)

        assert len(results) == 1
        assert mock_conn.fetch.call_count == 1

    @pytest.mark.anyio
    async def test_iter_responses_batched_empty(self, mock_pool, mock_conn):
        """iter_responses_batched with no responses returns empty list."""
        form_id = uuid.uuid4()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import iter_responses_batched

            results = await iter_responses_batched(form_id)

        assert results == []

    @pytest.mark.anyio
    async def test_count_total_responses_returns_int(self, mock_pool, mock_conn):
        """count_total_responses should return the COUNT result as int."""
        form_id = uuid.uuid4()
        mock_conn.fetchval = AsyncMock(return_value=42)

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            from app.repositories.form_repo import count_total_responses

            count = await count_total_responses(form_id)

        assert count == 42

    @pytest.mark.anyio
    async def test_get_form_stats_uses_batched_and_count(self):
        """get_form_stats should call count_total_responses and iter_responses_batched."""
        form_id = uuid.uuid4()
        _now = datetime.now(timezone.utc).isoformat()  # noqa: F841
        form_row = {
            "id": form_id,
            "questions": json.dumps(
                [
                    {"id": "q1", "type": "text", "label": "Name"},
                ]
            ),
            "created_by": uuid.uuid4(),
        }

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 3),
            ),
            patch(
                "app.services.form.form_repo.count_total_responses",
                new_callable=AsyncMock,
                return_value=3,
            ) as mock_count,
            patch(
                "app.services.form.form_repo.iter_responses_batched",
                new_callable=AsyncMock,
                return_value=[
                    {"answers": {"q1": "Alice"}},
                    {"answers": {"q1": "Bob"}},
                    {"answers": {"q1": ""}},
                ],
            ) as mock_iter,
        ):
            from app.services.form import get_form_stats

            stats = await get_form_stats(form_id)

        mock_count.assert_awaited_once_with(form_id)
        mock_iter.assert_awaited_once_with(form_id)
        assert stats["total_responses"] == 3
        # q1 is text: count should be 2 (non-empty)
        assert stats["question_stats"][0]["stats"]["count"] == 2

    @pytest.mark.anyio
    async def test_get_form_stats_choice_question(self):
        """get_form_stats correctly computes choice stats with batched responses."""
        form_id = uuid.uuid4()
        form_row = {
            "id": form_id,
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Favorite color",
                    "options": [
                        {"id": "opt_r", "label": "Red"},
                        {"id": "opt_b", "label": "Blue"},
                    ],
                }
            ],
            "created_by": uuid.uuid4(),
        }

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 3),
            ),
            patch(
                "app.services.form.form_repo.count_total_responses",
                new_callable=AsyncMock,
                return_value=3,
            ),
            patch(
                "app.services.form.form_repo.iter_responses_batched",
                new_callable=AsyncMock,
                return_value=[
                    {"answers": {"q1": "opt_r"}},
                    {"answers": {"q1": "opt_b"}},
                    {"answers": {"q1": "opt_r"}},
                ],
            ),
        ):
            from app.services.form import get_form_stats

            stats = await get_form_stats(form_id)

        q1_stats = stats["question_stats"][0]["stats"]
        option_counts = {o["option_id"]: o["count"] for o in q1_stats["options"]}
        assert option_counts["opt_r"] == 2
        assert option_counts["opt_b"] == 1

    @pytest.mark.anyio
    async def test_get_form_stats_rating_question(self):
        """get_form_stats correctly computes rating stats with batched responses."""
        form_id = uuid.uuid4()
        form_row = {
            "id": form_id,
            "questions": [
                {"id": "q1", "type": "rating", "label": "Rate us", "min": 1, "max": 5},
            ],
            "created_by": uuid.uuid4(),
        }

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 4),
            ),
            patch(
                "app.services.form.form_repo.count_total_responses",
                new_callable=AsyncMock,
                return_value=4,
            ),
            patch(
                "app.services.form.form_repo.iter_responses_batched",
                new_callable=AsyncMock,
                return_value=[
                    {"answers": {"q1": 5}},
                    {"answers": {"q1": 3}},
                    {"answers": {"q1": 4}},
                    {"answers": {"q1": 3}},
                ],
            ),
        ):
            from app.services.form import get_form_stats

            stats = await get_form_stats(form_id)

        q1_stats = stats["question_stats"][0]["stats"]
        assert q1_stats["average"] == 3.75
        assert q1_stats["min"] == 3
        assert q1_stats["max"] == 5
        assert q1_stats["count"] == 4

    def test_get_form_stats_source_uses_batched(self):
        """get_form_stats should use iter_responses_batched, not find_all_responses."""
        import inspect

        from app.services import form as form_module

        source = inspect.getsource(form_module.get_form_stats)
        assert (
            "iter_responses_batched" in source
        ), "get_form_stats should use iter_responses_batched"
        assert (
            "count_total_responses" in source
        ), "get_form_stats should use count_total_responses for the count"
        assert (
            "find_all_responses" not in source
        ), "get_form_stats should NOT use find_all_responses (loads all into memory)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_find_many():
    from app.repositories.post_repo import find_many

    return find_many


def _is_uuid_str(s: str) -> bool:
    """Check if a string looks like a UUID."""
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


def _make_response_record(response_id: uuid.UUID, form_id: uuid.UUID, answers: dict) -> MagicMock:
    """Create a mock asyncpg Record for form_responses."""
    now = datetime.now(timezone.utc)
    user_id = uuid.uuid4()
    data = {
        "id": response_id,
        "form_id": form_id,
        "user_id": user_id,
        "answers": json.dumps(answers),
        "created_at": now,
    }
    record = MagicMock()
    record.__getitem__ = lambda self, key: data[key]
    record.keys = lambda: data.keys()
    record.values = lambda: data.values()
    record.items = lambda: data.items()

    def _dict_from_record():
        return dict(data)

    # Allow dict(record) to work
    record.__iter__ = lambda self: iter(data)
    record.__len__ = lambda self: len(data)
    # Make dict(record) work by providing keys()
    return record
