"""Shared async runner for Celery tasks.

Celery workers use prefork with --max-memory-per-child, so each worker process
may handle many tasks before being recycled.  Creating a fresh event loop per
task via ``asyncio.run()`` destroys the loop when done, which invalidates any
asyncpg connections that were bound to it.  Instead, we lazily create **one**
event loop per worker process and reuse it for the lifetime of that process.

Usage (from any sync Celery task)::

    from app.tasks.async_runner import run_async

    result = run_async(some_coroutine())
"""

import asyncio
import threading
from typing import Any

_lock = threading.Lock()
_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_thread: threading.Thread | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """Return the per-worker event loop, creating it on first call."""
    global _worker_loop, _worker_thread

    with _lock:
        if _worker_loop is not None and not _worker_loop.is_closed():
            return _worker_loop

        _worker_loop = asyncio.new_event_loop()

        def _run_forever(loop: asyncio.AbstractEventLoop) -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        _worker_thread = threading.Thread(target=_run_forever, args=(_worker_loop,), daemon=True)
        _worker_thread.start()
        return _worker_loop


def run_async(coro: Any, timeout: float = 600) -> Any:
    """Run an async coroutine from a sync Celery task context.

    Uses a persistent per-worker event loop so that asyncpg connections
    created under that loop remain valid across multiple task invocations.

    Args:
        coro: The coroutine to run.
        timeout: Maximum seconds to wait (default matches Celery task_time_limit).
            Raises ``concurrent.futures.TimeoutError`` if exceeded.
    """
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)
