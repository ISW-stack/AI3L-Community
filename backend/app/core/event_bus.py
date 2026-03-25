import asyncio
import json
import time
import uuid as _uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, cast

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
    """Emit an event. Handlers run concurrently and are retried up to MAX_RETRIES times on failure.

    Returns EmitResult with details of any permanently failed handlers.
    Final failures are persisted to Redis (best-effort) for later inspection.
    """
    handlers = _handlers.get(event, [])
    if not handlers:
        return EmitResult()

    async def _run_handler(handler: Callable) -> HandlerFailure | None:
        handler_name = getattr(handler, "__name__", repr(handler))
        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES retries
            try:
                await handler(**kwargs)
                return None
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

        logger.error(
            "Event handler permanently failed after retries",
            exc_info=True,
            extra={
                "event": event,
                "handler": handler_name,
                "max_retries": MAX_RETRIES,
            },
        )
        if last_exc is None:  # pragma: no cover — cannot happen by logic
            last_exc = Exception("Unknown handler error")
        await _persist_failed_event(event, handler_name, kwargs, retry_count=0)
        return HandlerFailure(event, handler_name, last_exc, MAX_RETRIES + 1)

    outcomes = await asyncio.gather(*(_run_handler(h) for h in handlers))
    result = EmitResult()
    result.failures = [f for f in outcomes if f is not None]
    return result


# L-49: Keys whose values must be redacted before persisting to Redis
_REDACT_KEYS = frozenset({"content", "message", "body", "password", "token"})


def _redact_kwargs(kwargs: dict) -> dict:
    """Remove sensitive values from event kwargs before persisting."""
    redacted: dict = {}
    for k, v in kwargs.items():
        if k in _REDACT_KEYS:
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = _redact_kwargs(v)
        else:
            redacted[k] = v
    return redacted


async def _persist_failed_event(
    event: str, handler_name: str, kwargs: dict, *, retry_count: int = 0
) -> None:
    """Best-effort persistence of failed events to Redis for later retry."""
    try:
        from app.core.redis import get_redis

        redis = get_redis()
        entry = json.dumps(
            {
                "event_id": str(_uuid.uuid4()),  # L-48: dedup key
                "event": event,
                "handler": handler_name,
                "kwargs": _redact_kwargs(kwargs),  # L-49: redact sensitive fields for display
                "original_kwargs": kwargs,  # H-01: unredacted payload for retry
                "retry_count": retry_count,
                "timestamp": time.time(),
            },
            default=str,
        )
        _: Any = await cast(Awaitable[Any], redis.lpush("event_bus:failed", entry))
        _ = await cast(Awaitable[Any], redis.ltrim("event_bus:failed", 0, 999))  # Keep last 1000
        await redis.expire("event_bus:failed", 86400)  # 24h TTL
    except Exception:
        logger.debug("Failed to persist event failure to Redis", exc_info=True)


def clear() -> None:
    """Clear all registered handlers. For testing only."""
    _handlers.clear()
