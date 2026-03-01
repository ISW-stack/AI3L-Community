import asyncio
import json
from collections import defaultdict
from typing import Callable

from loguru import logger

_handlers: dict[str, list[Callable]] = defaultdict(list)

MAX_RETRIES = 2
RETRY_DELAY = 1.0  # seconds


def on(event: str, handler: Callable) -> None:
    """Register a handler for an event."""
    _handlers[event].append(handler)


async def emit(event: str, **kwargs) -> None:
    """Emit an event. Handlers are retried up to MAX_RETRIES times on failure.

    Final failures are persisted to Redis (best-effort) for later inspection.
    """
    for handler in _handlers.get(event, []):
        handler_name = getattr(handler, "__name__", repr(handler))
        success = False

        for attempt in range(1, MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES retries
            try:
                await handler(**kwargs)
                success = True
                break
            except Exception:
                logger.warning(
                    "Event handler failed",
                    exc_info=True,
                    extra={
                        "event": event,
                        "handler": handler_name,
                        "attempt": attempt,
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )
                if attempt <= MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)

        if not success:
            logger.error(
                "Event handler permanently failed after retries",
                extra={
                    "event": event,
                    "handler": handler_name,
                    "max_retries": MAX_RETRIES,
                },
            )
            await _persist_failed_event(event, handler_name, kwargs)


async def _persist_failed_event(event: str, handler_name: str, kwargs: dict) -> None:
    """Best-effort persistence of failed events to Redis for later inspection."""
    try:
        from app.core.redis import get_redis

        redis = get_redis()
        entry = json.dumps(
            {"event": event, "handler": handler_name, "kwargs_keys": list(kwargs.keys())},
            default=str,
        )
        await redis.lpush("event_bus:failed", entry)
        await redis.ltrim("event_bus:failed", 0, 999)  # Keep last 1000
        await redis.expire("event_bus:failed", 86400)  # 24h TTL
    except Exception:
        logger.debug("Failed to persist event failure to Redis", exc_info=True)


def clear() -> None:
    """Clear all registered handlers. For testing only."""
    _handlers.clear()
