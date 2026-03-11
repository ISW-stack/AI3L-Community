import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger

_handlers: dict[str, list[Callable]] = defaultdict(list)

MAX_RETRIES = 2
RETRY_DELAY = 1.0  # seconds


@dataclass
class HandlerFailure:
    """Details of a permanently failed event handler."""

    event: str
    handler_name: str
    exception: Exception
    attempts: int


@dataclass
class EmitResult:
    """Result of emitting an event, including any handler failures."""

    failures: list[HandlerFailure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.failures) == 0


def on(event: str, handler: Callable) -> None:
    """Register a handler for an event."""
    _handlers[event].append(handler)


async def emit(event: str, **kwargs: Any) -> EmitResult:
    """Emit an event. Handlers are retried up to MAX_RETRIES times on failure.

    Returns EmitResult with details of any permanently failed handlers.
    Final failures are persisted to Redis (best-effort) for later inspection.
    """
    result = EmitResult()

    for handler in _handlers.get(event, []):
        handler_name = getattr(handler, "__name__", repr(handler))
        success = False
        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES retries
            try:
                await handler(**kwargs)
                success = True
                break
            except Exception as exc:
                last_exc = exc
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
            if last_exc is None:  # pragma: no cover — cannot happen by logic
                last_exc = Exception("Unknown handler error")
            result.failures.append(HandlerFailure(event, handler_name, last_exc, MAX_RETRIES + 1))
            await _persist_failed_event(event, handler_name, kwargs, retry_count=0)

    return result


async def _persist_failed_event(
    event: str, handler_name: str, kwargs: dict, *, retry_count: int = 0
) -> None:
    """Best-effort persistence of failed events to Redis for later retry."""
    try:
        from app.core.redis import get_redis

        redis = get_redis()
        entry = json.dumps(
            {
                "event": event,
                "handler": handler_name,
                "kwargs": {k: v for k, v in kwargs.items()},
                "retry_count": retry_count,
            },
            default=str,
        )
        await redis.lpush("event_bus:failed", entry)  # type: ignore[misc]
        await redis.ltrim("event_bus:failed", 0, 999)  # type: ignore[misc]  # Keep last 1000
        await redis.expire("event_bus:failed", 86400)  # 24h TTL
    except Exception:
        logger.debug("Failed to persist event failure to Redis", exc_info=True)


def clear() -> None:
    """Clear all registered handlers. For testing only."""
    _handlers.clear()
