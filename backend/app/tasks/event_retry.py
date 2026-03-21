import json
import re
import uuid
from typing import Any, Awaitable, cast

from celery import shared_task
from loguru import logger

MAX_EVENT_RETRIES = 3
# Maximum events to process per invocation (prevents unbounded loops)
MAX_EVENTS_PER_RUN = 500

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _restore_types(kwargs: dict) -> dict:
    """Restore Python types lost during JSON serialization.

    UUIDs serialized via ``json.dumps(default=str)`` become plain strings.
    This function converts UUID-formatted strings back to ``uuid.UUID``.
    """
    restored: dict = {}
    for key, value in kwargs.items():
        if isinstance(value, str) and _UUID_RE.match(value):
            restored[key] = uuid.UUID(value)
        elif isinstance(value, dict):
            restored[key] = _restore_types(value)
        elif isinstance(value, list):
            restored[key] = [
                uuid.UUID(v) if isinstance(v, str) and _UUID_RE.match(v) else v for v in value
            ]
        else:
            restored[key] = value
    return restored


@shared_task(name="retry_failed_events")
def retry_failed_events() -> None:
    """Periodic task: retry failed events from Redis with bounded retries."""
    from app.tasks.async_runner import run_async

    run_async(_async_retry())


# L-48: TTL for dedup keys (10 minutes — covers multiple retry cycles)
_DEDUP_TTL = 600
_DEDUP_PREFIX = "event_bus:dedup:"


async def _async_retry() -> None:
    from app.core.event_bus import _handlers
    from app.core.redis import get_redis

    try:
        redis = get_redis()
    except Exception:
        logger.warning("Redis not available for event retry")
        return

    retried = 0
    dropped = 0
    re_failed = 0
    deduped = 0

    # Pop one event at a time — unprocessed events stay in Redis if worker crashes
    for _ in range(MAX_EVENTS_PER_RUN):
        raw: Any = await cast(Awaitable[Any], redis.lpop("event_bus:failed"))
        if raw is None:
            break

        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            dropped += 1
            continue

        # L-48: Skip already-processed events using event_id dedup
        event_id = entry.get("event_id")
        if event_id:
            dedup_key = f"{_DEDUP_PREFIX}{event_id}"
            already_seen: Any = await cast(
                Awaitable[Any], redis.set(dedup_key, "1", nx=True, ex=_DEDUP_TTL)
            )
            if not already_seen:
                deduped += 1
                continue

        retry_count = entry.get("retry_count", 0)
        if retry_count >= MAX_EVENT_RETRIES:
            logger.error(
                "Event permanently failed after %d retries, dropping",
                retry_count,
                extra={"event": entry.get("event"), "handler": entry.get("handler")},
            )
            dropped += 1
            continue

        event_name = entry.get("event")
        kwargs = _restore_types(entry.get("kwargs", {}))

        if not event_name or event_name not in _handlers:
            dropped += 1
            continue

        handler_name = entry.get("handler")

        matched_handler = None
        for handler in _handlers[event_name]:
            if getattr(handler, "__name__", repr(handler)) == handler_name:
                matched_handler = handler
                break

        if matched_handler is None:
            logger.warning(
                "Handler no longer registered, dropping event",
                extra={"event": event_name, "handler": handler_name},
            )
            dropped += 1
            continue

        try:
            await matched_handler(**kwargs)
            retried += 1
        except Exception:
            from app.core.event_bus import _persist_failed_event

            await _persist_failed_event(
                event_name,
                handler_name or "unknown",
                kwargs,
                retry_count=retry_count + 1,
            )
            re_failed += 1

    if retried or dropped or re_failed or deduped:
        logger.info(
            "Event retry complete",
            extra={
                "retried": retried,
                "dropped": dropped,
                "re_failed": re_failed,
                "deduped": deduped,
            },
        )
