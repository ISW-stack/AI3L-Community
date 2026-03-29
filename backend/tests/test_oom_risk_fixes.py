"""Tests for OOM risk audit fixes (C-1 through C-5)."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── C-1: Batched warmup_block_cache ───────────────────────────────────────────


class TestWarmupBlockCacheBatched:
    """C-1: warmup_block_cache should fetch in batches, not load entire table."""

    @pytest.mark.anyio
    async def test_warmup_fetches_in_batches(self, mock_pool, mock_conn):
        """warmup_block_cache uses LIMIT/OFFSET batching."""
        from app.core.blacklist import warmup_block_cache

        batch1 = [
            {"blocker_id": uuid.uuid4(), "blocked_id": uuid.uuid4()}
            for _ in range(3)
        ]

        # First fetch returns 3 rows (< batch size), so loop completes in 1 iteration
        mock_conn.fetch.return_value = batch1

        redis = MagicMock()
        pipe = AsyncMock()
        redis.pipeline = MagicMock(return_value=pipe)

        await warmup_block_cache(mock_pool, redis)

        # Verify LIMIT/OFFSET was used in the query
        call_args = mock_conn.fetch.call_args
        sql = call_args.args[0]
        assert "LIMIT" in sql
        assert "OFFSET" in sql

    @pytest.mark.anyio
    async def test_warmup_multiple_batches(self, mock_pool, mock_conn):
        """warmup_block_cache processes multiple batches when data exceeds batch size."""
        from app.core.blacklist import warmup_block_cache

        # Simulate 2 batches: first returns _BATCH_SIZE rows, second returns fewer
        batch_size = 5000
        full_batch = [
            {"blocker_id": uuid.uuid4(), "blocked_id": uuid.uuid4()}
            for _ in range(batch_size)
        ]
        partial_batch = [
            {"blocker_id": uuid.uuid4(), "blocked_id": uuid.uuid4()}
            for _ in range(10)
        ]

        mock_conn.fetch.side_effect = [full_batch, partial_batch]

        redis = MagicMock()
        pipe = AsyncMock()
        redis.pipeline = MagicMock(return_value=pipe)

        await warmup_block_cache(mock_pool, redis)

        # Should have made 2 fetch calls (2 batches)
        assert mock_conn.fetch.call_count == 2
        # Should have called pipeline.execute twice (once per batch)
        assert pipe.execute.call_count == 2

    @pytest.mark.anyio
    async def test_warmup_empty_table(self, mock_pool, mock_conn):
        """warmup_block_cache handles empty blocks table gracefully."""
        from app.core.blacklist import warmup_block_cache

        mock_conn.fetch.return_value = []

        redis = MagicMock()
        await warmup_block_cache(mock_pool, redis)
        redis.pipeline.assert_not_called()


# ── C-2: Batched album photo iteration ────────────────────────────────────────


class TestAlbumPhotoBatchedIteration:
    """C-2: iter_photos_for_album_batched should fetch in chunks."""

    @pytest.mark.anyio
    async def test_iter_photos_single_batch(self):
        """Returns one batch when photos < batch_size."""
        from app.repositories.album_repo import iter_photos_for_album_batched

        conn = AsyncMock()
        photos = [
            {"id": uuid.uuid4(), "storage_key": f"key_{i}",
             "thumbnail_key": None, "file_size_bytes": 100, "uploaded_by": uuid.uuid4()}
            for i in range(3)
        ]
        conn.fetch.return_value = photos

        batches = await iter_photos_for_album_batched(conn, uuid.uuid4(), batch_size=500)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    @pytest.mark.anyio
    async def test_iter_photos_multiple_batches(self):
        """Processes multiple batches when photos exceed batch_size."""
        from app.repositories.album_repo import iter_photos_for_album_batched

        conn = AsyncMock()

        def make_photo():
            return {"id": uuid.uuid4(), "storage_key": "k",
                    "thumbnail_key": None, "file_size_bytes": 100,
                    "uploaded_by": uuid.uuid4()}

        batch1 = [make_photo() for _ in range(5)]
        batch2 = [make_photo() for _ in range(2)]

        conn.fetch.side_effect = [batch1, batch2]

        batches = await iter_photos_for_album_batched(conn, uuid.uuid4(), batch_size=5)
        assert len(batches) == 2
        assert len(batches[0]) == 5
        assert len(batches[1]) == 2

    @pytest.mark.anyio
    async def test_iter_photos_empty_album(self):
        """Returns empty list for album with no photos."""
        from app.repositories.album_repo import iter_photos_for_album_batched

        conn = AsyncMock()
        conn.fetch.return_value = []

        batches = await iter_photos_for_album_batched(conn, uuid.uuid4())
        assert batches == []

    @pytest.mark.anyio
    async def test_iter_photos_uses_limit_offset(self):
        """Verify SQL contains LIMIT and OFFSET."""
        from app.repositories.album_repo import iter_photos_for_album_batched

        conn = AsyncMock()
        conn.fetch.return_value = []

        await iter_photos_for_album_batched(conn, uuid.uuid4(), batch_size=100)

        sql = conn.fetch.call_args.args[0]
        assert "LIMIT" in sql
        assert "OFFSET" in sql


# ── C-3: Citation LIMIT ──────────────────────────────────────────────────────


class TestCitationLimit:
    """C-3: find_existing_citations should have a LIMIT parameter."""

    @pytest.mark.anyio
    async def test_find_existing_citations_has_limit(self):
        """SQL query includes LIMIT clause."""
        from app.repositories.citation_repo import find_existing_citations

        conn = AsyncMock()
        conn.fetch.return_value = []

        await find_existing_citations(conn, uuid.uuid4())

        sql = conn.fetch.call_args.args[0]
        assert "LIMIT" in sql

    @pytest.mark.anyio
    async def test_find_existing_citations_custom_limit(self):
        """Custom limit parameter is passed to query."""
        from app.repositories.citation_repo import find_existing_citations

        conn = AsyncMock()
        conn.fetch.return_value = []

        await find_existing_citations(conn, uuid.uuid4(), limit=100)

        # Second positional arg after post_id should be 100
        args = conn.fetch.call_args.args
        assert args[2] == 100


# ── C-4: BytesIO upload pattern ───────────────────────────────────────────────


class TestAlbumUploadBytesIO:
    """C-4: Album upload endpoints should use BytesIO instead of chunk list."""

    def test_no_chunks_list_pattern_in_albums(self):
        """Verify the old chunks: list[bytes] pattern is no longer used."""
        import inspect

        from app.api.v1.endpoints import albums

        source = inspect.getsource(albums)
        assert "chunks: list[bytes]" not in source
        assert "chunks.append" not in source

    def test_bytesio_import_in_albums(self):
        """Verify io module is imported for BytesIO usage."""
        from app.api.v1.endpoints import albums

        assert hasattr(albums, "io")


# ── C-5: download_file size guard ─────────────────────────────────────────────


class TestDownloadFileSizeGuard:
    """C-5: download_file should validate size before reading."""

    def test_download_file_rejects_oversized(self):
        """download_file raises ValueError when ContentLength exceeds max_size."""
        from app.core.storage import download_file

        mock_body = MagicMock()
        mock_resp = {
            "Body": mock_body,
            "ContentType": "application/pdf",
            "ContentLength": 200 * 1024 * 1024,  # 200 MB
        }

        with patch("app.core.storage.get_storage") as mock_storage:
            mock_storage.return_value.get_object.return_value = mock_resp

            with pytest.raises(ValueError, match="too large"):
                download_file("some/key.pdf", max_size=100 * 1024 * 1024)

            mock_body.close.assert_called_once()

    def test_download_file_accepts_within_limit(self):
        """download_file succeeds when file is within max_size."""
        from app.core.storage import download_file

        test_data = b"hello world"
        mock_body = MagicMock()
        mock_body.iter_chunks.return_value = [test_data]
        mock_resp = {
            "Body": mock_body,
            "ContentType": "text/plain",
            "ContentLength": len(test_data),
        }

        with patch("app.core.storage.get_storage") as mock_storage:
            mock_storage.return_value.get_object.return_value = mock_resp
            data, ct = download_file("some/key.txt")

            assert data == test_data
            assert ct == "text/plain"
            mock_body.close.assert_called_once()

    def test_download_file_custom_max_size(self):
        """download_file respects custom max_size parameter."""
        from app.core.storage import download_file

        mock_body = MagicMock()
        mock_resp = {
            "Body": mock_body,
            "ContentType": "application/octet-stream",
            "ContentLength": 5000,
        }

        with patch("app.core.storage.get_storage") as mock_storage:
            mock_storage.return_value.get_object.return_value = mock_resp

            with pytest.raises(ValueError, match="too large"):
                download_file("some/key", max_size=1000)

    def test_download_file_enforces_during_read(self):
        """download_file catches size exceeded during chunked read."""
        from app.core.storage import download_file

        # ContentLength says 100, but actual data is 2000
        mock_body = MagicMock()
        mock_body.iter_chunks.return_value = [b"x" * 1000, b"y" * 1000]
        mock_resp = {
            "Body": mock_body,
            "ContentType": "text/plain",
            "ContentLength": 100,
        }

        with patch("app.core.storage.get_storage") as mock_storage:
            mock_storage.return_value.get_object.return_value = mock_resp

            with pytest.raises(ValueError, match="exceeded"):
                download_file("some/key", max_size=500)


# ── H-1: Recommendations cursor-based user fetch ─────────────────────────────


class TestRecommendationsCursorBasedFetch:
    """H-1: recommendations task should use cursor-based batching, not load all user IDs."""

    def test_recommendation_sql_uses_cursor_pattern(self):
        """Verify the recommendation task uses id > $1 ORDER BY id LIMIT pattern."""
        import inspect

        from app.tasks import recommendations

        source = inspect.getsource(recommendations)
        # Should use cursor pattern (id > $1) instead of fetching all IDs at once
        assert "id > $1" in source or "id > $" in source
        # Should NOT have the old pattern of fetching all user IDs
        assert "user_ids = [" not in source


# ── H-4: Posts page parameter upper bound ─────────────────────────────────────


class TestPostsPageUpperBound:
    """H-4: All paginated endpoints should cap page at 1000, not 10000."""

    def test_posts_endpoint_max_page_1000(self):
        """Verify posts endpoint page parameter le=1000."""
        import inspect

        from app.api.v1.endpoints import posts

        source = inspect.getsource(posts.get_posts_list)
        assert "le=1000" in source
        assert "le=10000" not in source

    def test_no_endpoint_uses_le_10000(self):
        """Verify no endpoint file still uses le=10000 for page parameter."""
        import os

        endpoint_dir = os.path.join(
            os.path.dirname(__file__), "..", "app", "api", "v1", "endpoints"
        )
        for fname in os.listdir(endpoint_dir):
            if not fname.endswith(".py"):
                continue
            with open(os.path.join(endpoint_dir, fname), encoding="utf-8") as f:
                content = f.read()
            # le=10000 should not appear in any page Query parameter
            if "page" in content and "le=10000" in content:
                pytest.fail(f"{fname} still uses le=10000 for page parameter")


# ── H-5: Site export always uses multipart upload ─────────────────────────────


class TestSiteExportAlwaysMultipart:
    """H-5: site_export should always use multipart upload, never load full ZIP."""

    def test_no_full_file_read_pattern(self):
        """Verify the old data = f.read() pattern is gone from site_export."""
        import inspect

        from app.tasks import site_export

        source = inspect.getsource(site_export)
        # Old pattern: read entire file then upload
        assert "upload_file(data," not in source
        # Should always go through multipart
        assert "create_multipart_upload" in source
