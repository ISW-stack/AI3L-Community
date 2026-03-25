import asyncio
import json
import re
import uuid
from typing import Any, Awaitable, cast

from celery import shared_task
from loguru import logger

MAX_EVENT_RETRIES = 3
# Maximum events to process per invocation (prevents unbounded loops)
MAX_EVENTS_PER_RUN = 500


async def _ensure_redis() -> None:
    """Ensure Redis is initialized in the Celery worker process."""
    from app.core.config import settings
    from app.core.redis import get_redis, init_redis

    try:
        get_redis()
    except RuntimeError:
        await init_redis(settings.REDIS_URL)

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

    # L-13: Ensure Redis is initialized before use in Celery worker
    await _ensure_redis()

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
        # H-01: Use original_kwargs (unredacted) for retry if available,
        # falling back to kwargs for backward compatibility with old entries
        raw_kwargs = entry.get("original_kwargs") or entry.get("kwargs", {})
        kwargs = _restore_types(raw_kwargs)

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


# ── L-50: SIG notification Celery task ───────────────────────────────────

_SIG_MEMBER_BATCH_SIZE = 200
_SIG_NOTIFICATION_MAX = 500
_SIG_NOTIFICATION_CONCURRENCY = 20


@shared_task(name="notify_sig_members_new_post", bind=True, max_retries=2)
def notify_sig_members_new_post(
    self: Any,
    sig_id: str,
    post_id: str,
    author_id: str,
    post_title: str,
) -> dict[str, int]:
    """Celery task: notify SIG members about a new post in batches.

    Offloaded from the event bus so large SIGs don't block event processing.
    """
    from app.tasks.async_runner import run_async

    return cast(
        dict[str, int],
        run_async(_async_notify_sig_members(sig_id, post_id, author_id, post_title)),
    )


async def _is_blocked_for_sig(user_a: str, user_b: str) -> bool:
    """Check block status for SIG notification (same as event_handlers._is_blocked)."""
    try:
        from app.core.blacklist import get_blocked_user_ids
        from app.core.database import get_pool
        from app.core.redis import get_redis

        redis = get_redis()
        pool = get_pool()
        blocked = await get_blocked_user_ids(redis, user_a, pool=pool)
        return user_b in blocked
    except Exception:
        return False


async def _check_idempotent_for_sig(
    user_id: str, entity_type: str | None, entity_id: str | None, action: str
) -> bool:
    """Dedup check for SIG notification (same as event_handlers._check_idempotent)."""
    try:
        from app.core.redis import get_redis

        redis = get_redis()
        key = f"notify:idempotent:{user_id}:{entity_type}:{entity_id}:{action}"
        result = await redis.set(key, "1", ex=300, nx=True)
        return result is not None
    except Exception:
        return True


async def _async_notify_sig_members(
    sig_id: str,
    post_id: str,
    author_id: str,
    post_title: str,
) -> dict[str, int]:
    """Async implementation: batch-notify SIG members about a new post."""
    from app.tasks.utils import ensure_pool

    await ensure_pool()
    # H-06: Ensure Redis is initialized before helper functions call get_redis()
    await _ensure_redis()

    from app.repositories import sig_repo
    from app.services.notification import create_notification
    from app.services.user import get_user_by_id

    author = await get_user_by_id(uuid.UUID(author_id))
    author_name = author["display_name"] if author else "Someone"

    sem = asyncio.Semaphore(_SIG_NOTIFICATION_CONCURRENCY)
    succeeded = 0
    failed = 0
    notified_count = 0
    cap_reached = False

    async def _notify_member(target_uid: str) -> bool:
        async with sem:
            if await _is_blocked_for_sig(target_uid, author_id):
                return True
            if not await _check_idempotent_for_sig(target_uid, "post", post_id, "SIG_NEW_POST"):
                return True
            try:
                await create_notification(
                    user_id=target_uid,
                    trigger_user_id=author_id,
                    action_type="SIG_NEW_POST",
                    entity_type="post",
                    entity_id=post_id,
                    message=f'{author_name} posted "{post_title[:50]}" in your SIG',
                )
                return True
            except (ConnectionError, OSError, TimeoutError) as e:
                logger.warning(
                    "Transient error sending SIG new post notification (retryable)",
                    extra={"target_uid": target_uid, "error": str(e)},
                )
                return False
            except Exception:
                logger.error("Failed to send SIG new post notification", exc_info=True)
                return False

    offset = 0
    while True:
        members, _total = await sig_repo.find_members(
            uuid.UUID(sig_id), offset=offset, limit=_SIG_MEMBER_BATCH_SIZE
        )
        if not members:
            break

        tasks: list[asyncio.Task[bool]] = []
        for m in members:
            target_uid = str(m["user_id"])
            if target_uid == author_id:
                continue
            notified_count += 1
            if notified_count > _SIG_NOTIFICATION_MAX:
                cap_reached = True
                break
            tasks.append(asyncio.create_task(_notify_member(target_uid)))

        if tasks:
            results = await asyncio.gather(*tasks)
            for ok in results:
                if ok:
                    succeeded += 1
                else:
                    failed += 1

        if cap_reached:
            logger.warning(
                "SIG notification cap reached",
                extra={"sig_id": sig_id, "cap": _SIG_NOTIFICATION_MAX},
            )
            break

        if len(members) < _SIG_MEMBER_BATCH_SIZE:
            break

        offset += _SIG_MEMBER_BATCH_SIZE

    if failed:
        logger.error(
            "notify_sig_members_new_post summary",
            extra={"succeeded": succeeded, "failed": failed},
        )

    return {"succeeded": succeeded, "failed": failed}
