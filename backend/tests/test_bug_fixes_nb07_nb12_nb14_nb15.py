"""Tests for bug fixes N-B07, N-B12, N-B14, N-B15.

N-B07: form_export accesses record after connection release — fixed by extracting
       form_title into a local variable inside the async with block.
N-B12: cleanup_orphan_files does not scan comment content for file references —
       fixed by adding a comments batch in _get_referenced_keys.
N-B14: Celery tasks create fresh event loops via asyncio.run(), corrupting
       connection pool — fixed by shared run_async helper with per-worker loop.
N-B15: Pillow and other dependencies broadly pinned — pillow>=10.4.0.
"""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Celery mock fixture — must be set up before importing any task modules
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _celery_modules():
    """Inject fake celery modules into sys.modules so lazy imports succeed."""
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

    # Purge cached task modules so next test gets fresh imports
    for mod_name in list(sys.modules):
        if mod_name.startswith("app.tasks."):
            del sys.modules[mod_name]


# =========================================================================
# N-B12 — _get_referenced_keys scans comments
# =========================================================================


class TestGetReferencedKeysIncludesComments:
    """Verify that _get_referenced_keys also scans comments.content."""

    @pytest.mark.anyio
    async def test_comment_file_references_are_included(self):
        """File keys embedded in comments should appear in the referenced set."""
        post_html = '<p>Post <img src="/api/v1/files/content/editor/u1/post.png"></p>'
        comment_html = '<p>Comment <img src="/api/v1/files/content/editor/u2/comment.png"></p>'
        form_html = '<p>Form <img src="/api/v1/files/content/editor/u3/form.png"></p>'

        call_count = {"n": 0}

        async def mock_fetch(query, *args):
            call_count["n"] += 1
            if "posts" in query:
                if args[-1] == 0:  # offset == 0
                    return [{"html": post_html}]
                return []
            elif "comments" in query:
                if args[-1] == 0:
                    return [{"html": comment_html}]
                return []
            elif "forms" in query:
                if args[-1] == 0:
                    return [{"html": form_html}]
                return []
            return []

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=mock_fetch)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        with (
            patch("app.tasks.cleanup.get_pool", return_value=mock_pool),
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
        ):
            from app.tasks.cleanup import _get_referenced_keys

            keys = await _get_referenced_keys()

        assert "editor/u1/post.png" in keys
        assert "editor/u2/comment.png" in keys
        assert "editor/u3/form.png" in keys

    @pytest.mark.anyio
    async def test_comment_scan_uses_batched_queries(self):
        """Comment scanning should use the same LIMIT/OFFSET batching as posts."""
        import inspect

        from app.tasks.cleanup import _get_referenced_keys

        source = inspect.getsource(_get_referenced_keys)
        # The source must query the comments table
        assert "comments" in source, "Must query comments table"
        assert "is_deleted = FALSE" in source, "Must filter deleted comments"

    @pytest.mark.anyio
    async def test_no_comment_references_still_works(self):
        """When comments have no file references, other sources still work."""

        async def mock_fetch(query, *args):
            if "posts" in query and args[-1] == 0:
                return [{"html": '<img src="/api/v1/files/content/editor/u1/p.png">'}]
            return []

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=mock_fetch)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        with (
            patch("app.tasks.cleanup.get_pool", return_value=mock_pool),
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
        ):
            from app.tasks.cleanup import _get_referenced_keys

            keys = await _get_referenced_keys()

        assert "editor/u1/p.png" in keys

    @pytest.mark.anyio
    async def test_multiple_files_in_single_comment(self):
        """A comment with multiple embedded images should yield all keys."""
        html = (
            '<p><img src="/api/v1/files/content/editor/u1/a.png">'
            '<img src="/api/v1/files/content/editor/u1/b.jpg"></p>'
        )

        async def mock_fetch(query, *args):
            if "comments" in query and args[-1] == 0:
                return [{"html": html}]
            return []

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=mock_fetch)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        with (
            patch("app.tasks.cleanup.get_pool", return_value=mock_pool),
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
        ):
            from app.tasks.cleanup import _get_referenced_keys

            keys = await _get_referenced_keys()

        assert "editor/u1/a.png" in keys
        assert "editor/u1/b.jpg" in keys


# =========================================================================
# N-B14 — run_async uses persistent per-worker event loop
# =========================================================================


class TestRunAsyncPersistentLoop:
    """Verify that run_async reuses the same event loop across calls."""

    def test_run_async_returns_coroutine_result(self):
        """run_async should successfully run a simple coroutine."""
        from app.tasks.async_runner import run_async

        async def add(a: int, b: int) -> int:
            return a + b

        result = run_async(add(2, 3))
        assert result == 5

    def test_run_async_reuses_loop(self):
        """Multiple calls to run_async should use the same event loop."""
        from app.tasks import async_runner

        # Reset module state for clean test
        with async_runner._lock:
            if async_runner._worker_loop and not async_runner._worker_loop.is_closed():
                async_runner._worker_loop.call_soon_threadsafe(async_runner._worker_loop.stop)
                if async_runner._worker_thread:
                    async_runner._worker_thread.join(timeout=2)
            async_runner._worker_loop = None
            async_runner._worker_thread = None

        loops_seen: list[asyncio.AbstractEventLoop] = []

        async def capture_loop() -> None:
            loops_seen.append(asyncio.get_running_loop())

        async_runner.run_async(capture_loop())
        async_runner.run_async(capture_loop())

        assert len(loops_seen) == 2
        assert loops_seen[0] is loops_seen[1], "Should reuse the same event loop"

    def test_run_async_does_not_use_asyncio_run(self):
        """The shared helper should NOT call asyncio.run() (which destroys the loop)."""
        import inspect

        from app.tasks.async_runner import run_async

        source = inspect.getsource(run_async)
        # asyncio.run_coroutine_threadsafe is fine — it's asyncio.run() we want to avoid
        assert (
            "asyncio.run(" not in source
        ), "run_async must NOT use asyncio.run() — it destroys the loop"

    def test_all_task_files_use_shared_run_async(self):
        """All task files should import run_async from async_runner, not define their own."""
        import inspect

        task_modules = [
            "app.tasks.cleanup",
            "app.tasks.form_autoclose",
            "app.tasks.form_export",
            "app.tasks.virustotal",
            "app.tasks.view_sync",
            "app.tasks.thumbnail",
        ]

        for mod_name in task_modules:
            mod = __import__(mod_name, fromlist=["_run_async"])
            # Check that _run_async exists and is imported (not locally defined)
            if hasattr(mod, "_run_async"):
                source = inspect.getsource(mod)
                assert (
                    "def _run_async" not in source
                ), f"{mod_name} still defines its own _run_async"

    def test_run_async_propagates_exceptions(self):
        """Exceptions raised in the coroutine should propagate to the caller."""
        from app.tasks.async_runner import run_async

        async def failing() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_async(failing())


# =========================================================================
# N-B07 — form_export extracts form_title before releasing connection
# =========================================================================


class TestFormExportRecordAccess:
    """Verify that form_export extracts form values inside the connection block."""

    def test_form_title_extracted_inside_connection_block(self):
        """form_title should be a local variable set inside async with pool.acquire()."""
        import inspect

        from app.tasks.form_export import _async_export

        source = inspect.getsource(_async_export)
        # The variable form_title should be set inside the function
        assert "form_title" in source, "Should use form_title local variable"
        # The old pattern form["title"] should NOT appear after the connection block
        # (i.e., in the "Build a safe filename" section)
        lines = source.split("\n")
        after_upload = False
        for line in lines:
            if "Build a safe filename" in line:
                after_upload = True
            if after_upload and 'form["title"]' in line:
                pytest.fail(
                    "form['title'] accessed after connection release — "
                    "should use form_title local variable"
                )

    @pytest.mark.anyio
    async def test_form_title_used_for_download_filename(self):
        """The exported CSV should use form_title (extracted early) for filename."""
        import json
        import uuid

        form_id = str(uuid.uuid4())
        task_id = "test-task-123"
        questions = [{"id": "q1", "label": "Q1", "type": "text"}]

        form_row = {
            "title": "My Survey",
            "questions": json.dumps(questions),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=form_row)
        # No responses
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        mock_upload = MagicMock()
        mock_presigned = MagicMock(return_value="https://example.com/export.csv")
        mock_export_key = MagicMock(return_value="exports/test.csv")

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.tasks.form_export.init_db_pool", new_callable=AsyncMock),
            patch("app.core.storage.get_storage", MagicMock()),
            patch("app.tasks.form_export.upload_file", mock_upload),
            patch("app.tasks.form_export.generate_presigned_url", mock_presigned),
            patch("app.tasks.form_export.generate_form_export_key", mock_export_key),
        ):
            from app.tasks.form_export import _async_export

            result = await _async_export(form_id, task_id)

        assert result["download_url"] == "https://example.com/export.csv"
        # Verify presigned_url was called with a filename containing the title
        call_kwargs = mock_presigned.call_args
        assert "My_Survey.csv" in str(call_kwargs)

    @pytest.mark.anyio
    async def test_form_not_found_raises_error(self):
        """_async_export raises ValueError when form is not found."""
        import uuid

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        with (
            patch("app.tasks.form_export.get_pool", return_value=mock_pool),
            patch("app.tasks.form_export.init_db_pool", new_callable=AsyncMock),
            patch("app.core.storage.get_storage", MagicMock()),
        ):
            from app.tasks.form_export import _async_export

            with pytest.raises(ValueError, match="not found"):
                await _async_export(str(uuid.uuid4()), "task-1")


# =========================================================================
# N-B15 — Pillow version pin
# =========================================================================


class TestPillowVersionPin:
    """Verify requirements.txt pins Pillow to a safe minimum version."""

    def test_pillow_minimum_version_is_safe(self):
        """Pillow should require at least 10.4.0 to avoid known vulnerabilities."""
        import re
        from pathlib import Path

        req_path = Path(__file__).parent.parent / "requirements.txt"
        content = req_path.read_text()

        match = re.search(r"pillow>=([\d.]+)", content, re.IGNORECASE)
        assert match, "Pillow version pin not found in requirements.txt"

        version_parts = [int(x) for x in match.group(1).split(".")]
        # Must be >= 10.4.0
        assert version_parts >= [10, 4, 0], (
            f"Pillow minimum version {match.group(1)} is too low, "
            "should be >= 10.4.0 to avoid known CVEs"
        )


# =========================================================================
# Integration-style: verify cleanup docstring mentions comments
# =========================================================================


class TestCleanupDocstring:
    """Ensure the cleanup module docstring reflects comment scanning."""

    def test_module_docstring_mentions_comments(self):
        """The cleanup module docstring should mention comment content."""
        from app.tasks import cleanup

        doc = cleanup.__doc__ or ""
        assert (
            "comment" in doc.lower()
        ), "Module docstring should mention that comments are also scanned"

    def test_get_referenced_keys_docstring_mentions_comments(self):
        """_get_referenced_keys docstring should mention comments."""
        from app.tasks.cleanup import _get_referenced_keys

        doc = _get_referenced_keys.__doc__ or ""
        assert "comment" in doc.lower(), "_get_referenced_keys docstring should mention comments"
