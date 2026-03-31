import asyncio
import uuid
from typing import Any

import asyncpg
from loguru import logger

from app.converters.event_converter import async_row_to_event
from app.converters.shared import fill_user_reactions
from app.core.constants import RATE_LIMIT_EVENT_CREATE
from app.core.errors import RateLimitError
from app.core.event_bus import emit
from app.core.rate_limit import check_rate_limit
from app.repositories import event_repo

# Re-export for endpoint use
__all__ = ["_UNSET"]

_UNSET: Any = object()  # sentinel for "not provided"


async def create_event(
    user_id: str,
    title: str,
    content: str,
    sig_id: str | None = None,
    visibility: list[str] | None = None,
    allow_comments: bool = True,
) -> dict:
    if visibility is None:
        raise ValueError("Visibility must include at least one role.")

    if not await check_rate_limit(
        f"rl:event_create:{user_id}", *RATE_LIMIT_EVENT_CREATE
    ):
        raise RateLimitError("Too many event creation requests.")

    event_id = uuid.uuid4()
    sig_uuid = uuid.UUID(sig_id) if sig_id else None

    try:
        row = await event_repo.insert(
            event_id=event_id,
            user_id=uuid.UUID(user_id),
            title=title,
            content=content,
            sig_id=sig_uuid,
            visibility=visibility,
            allow_comments=allow_comments,
        )
    except asyncpg.exceptions.ForeignKeyViolationError:
        raise ValueError("SIG not found or has been deleted.")

    logger.info("Event created", extra={"event_id": str(event_id), "user_id": user_id})

    try:
        await emit(
            "audit.action",
            user_id=user_id,
            action="USER_CREATE_EVENT",
            target_type="event",
            target_id=str(event_id),
        )
    except Exception:
        logger.error("Failed to emit event.created audit", exc_info=True)

    return await async_row_to_event(row)


async def get_event(
    event_id: uuid.UUID,
    viewer_id: str | None = None,
    user_role: str | None = None,
) -> dict | None:
    row = await event_repo.find_by_id(event_id, user_role=user_role)
    if not row:
        return None
    result = await async_row_to_event(row)
    return fill_user_reactions(result, viewer_id)


async def list_events(
    page: int = 1,
    page_size: int = 20,
    sig_id: str | None = None,
    user_role: str | None = None,
    viewer_id: str | None = None,
) -> dict:
    sig_uuid = uuid.UUID(sig_id) if sig_id else None
    data = await event_repo.find_many(
        page=page,
        page_size=page_size,
        sig_id=sig_uuid,
        user_role=user_role,
    )
    events = list(
        await asyncio.gather(*[async_row_to_event(r) for r in data["events"]])
    )
    if viewer_id:
        events = [fill_user_reactions(e, viewer_id) for e in events]
    return {"events": events, "total": data["total"]}


async def update_event(
    event_id: uuid.UUID,
    user_id: str,
    caller_role: str,
    title: str | None = None,
    content: str | None = None,
    sig_id: Any = _UNSET,
    visibility: list[str] | None = None,
    allow_comments: bool | None = None,
    expected_version: int = 1,
) -> dict:
    # Permission pre-check (the real lock is inside event_repo.update)
    current = await event_repo.find_by_id(event_id)
    if not current:
        raise ValueError("Event not found.")

    is_owner = str(current["user_id"]) == user_id
    is_super_admin = caller_role == "SUPER_ADMIN"
    if not is_owner and not is_super_admin:
        raise PermissionError("Only the event creator or a Super Admin can edit this event.")

    # _UNSET → not provided, repo preserves current value (pass _UNSET through)
    # None → explicitly clear SIG
    # str → set to this SIG UUID
    if sig_id is _UNSET:
        sig_uuid: Any = _UNSET
    elif sig_id:
        sig_uuid = uuid.UUID(sig_id)
    else:
        sig_uuid = None  # explicit clear

    try:
        row = await event_repo.update(
            event_id=event_id,
            title=title,
            content=content,
            sig_id=sig_uuid,
            visibility=visibility,
            allow_comments=allow_comments,
            version=expected_version,
        )
    except ValueError:
        raise
    except asyncpg.exceptions.ForeignKeyViolationError:
        raise ValueError("SIG not found or has been deleted.")

    if not row:
        raise ValueError("Event not found.")

    logger.info("Event updated", extra={"event_id": str(event_id)})
    return await async_row_to_event(row)


async def delete_event(
    event_id: uuid.UUID,
    user_id: str,
    caller_role: str,
) -> bool:
    current = await event_repo.find_by_id(event_id)
    if not current:
        raise ValueError("Event not found.")

    is_owner = str(current["user_id"]) == user_id
    is_super_admin = caller_role == "SUPER_ADMIN"
    if not is_owner and not is_super_admin:
        raise PermissionError("Only the event creator or a Super Admin can delete this event.")

    result = await event_repo.soft_delete(event_id)
    if result:
        logger.info("Event deleted", extra={"event_id": str(event_id)})
    return result


async def toggle_event_reaction(
    event_id: uuid.UUID,
    user_id: str,
    reaction: str,
) -> dict | None:
    row = await event_repo.update_reactions(event_id, user_id, reaction)
    if not row:
        return None
    result = await async_row_to_event(row)
    return fill_user_reactions(result, user_id)
