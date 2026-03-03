import json

from celery import shared_task
from loguru import logger

MAX_EVENT_RETRIES = 3


@shared_task(name="retry_failed_events")
def retry_failed_events():
    """Periodic task: retry failed events from Redis with bounded retries."""
    from concurrent.futures import ThreadPoolExecutor
    import asyncio

    def _run():
        return asyncio.run(_async_retry())

    with ThreadPoolExecutor(1) as pool:
        pool.submit(_run).result()


async def _async_retry():
    from app.core.redis import get_redis
    from app.core.event_bus import _handlers

    try:
        redis = get_redis()
    except Exception:
        logger.warning("Redis not available for event retry")
        return

    raw_events = await redis.lrange("event_bus:failed", 0, -1)
    if not raw_events:
        return

    await redis.delete("event_bus:failed")

    retried = 0
    dropped = 0
    re_failed = 0

    for raw in raw_events:
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            dropped += 1
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
        kwargs = entry.get("kwargs", {})

        if not event_name or event_name not in _handlers:
            dropped += 1
            continue

        try:
            for handler in _handlers[event_name]:
                await handler(**kwargs)
            retried += 1
        except Exception:
            from app.core.event_bus import _persist_failed_event

            await _persist_failed_event(
                event_name,
                entry.get("handler", "unknown"),
                kwargs,
                retry_count=retry_count + 1,
            )
            re_failed += 1

    if retried or dropped or re_failed:
        logger.info(
            "Event retry complete",
            extra={"retried": retried, "dropped": dropped, "re_failed": re_failed},
        )
