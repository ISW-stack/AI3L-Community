import asyncio
import uuid
from typing import Any

import asyncpg
from loguru import logger

from app.converters.sig_converter import async_row_to_member, row_to_sig
from app.core.database import get_pool
from app.core.event_bus import emit
from app.repositories import sig_repo
from app.services.org_chart import invalidate_org_chart_cache

_UNSET: Any = object()  # sentinel: parameter was not supplied by caller


async def create_sig(name: str, description: str | None, creator_id: str) -> dict:
    pool = get_pool()
    sig_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_uuid = uuid.UUID(creator_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                row = await sig_repo.insert(sig_id, name, description, creator_uuid, conn)
            except asyncpg.UniqueViolationError:
                raise ValueError("A SIG with this name already exists.")
            await sig_repo.add_member(member_id, sig_id, creator_uuid, "ADMIN", conn)
            creator_name = await sig_repo.find_creator_display_name(creator_uuid, conn)

            logger.info("SIG created", extra={"sig_id": str(sig_id), "name": name})
            result = row_to_sig(row, creator_name)
    await invalidate_org_chart_cache()
    return result


async def list_sigs(offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    rows, total = await sig_repo.find_many(offset, limit)
    return [row_to_sig(r, r.get("creator_display_name")) for r in rows], total


async def get_sig_by_id(sig_id: uuid.UUID) -> dict | None:
    row = await sig_repo.find_by_id(sig_id)
    if not row:
        return None
    return row_to_sig(row, row.get("creator_display_name"))


async def update_sig(
    sig_id: uuid.UUID,
    name: Any = _UNSET,
    description: Any = _UNSET,
    caller_id: str | None = None,
    caller_role: str | None = None,
) -> dict | None:
    """Update a SIG's name/description.

    When caller_id and caller_role are provided, the SIG admin permission
    check is performed inside the same transaction as the update to prevent
    TOCTOU race conditions.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Permission check inside the transaction
            if caller_id and caller_role:
                is_global_admin = caller_role in ("SUPER_ADMIN", "ADMIN")
                if not is_global_admin:
                    sig_role = await sig_repo.get_member_role_in_conn(
                        sig_id, uuid.UUID(caller_id), conn
                    )
                    if sig_role != "ADMIN":
                        raise PermissionError("Not authorized.")

            # Read current values inside the transaction to prevent TOCTOU race
            current = await conn.fetchrow(
                """
                SELECT s.*, u.display_name AS creator_display_name
                FROM sigs s
                LEFT JOIN users u ON s.created_by = u.id
                WHERE s.id = $1 AND s.is_deleted = false
                """,
                sig_id,
            )
            if not current:
                return None
            new_name = name if name is not _UNSET else current["name"]
            new_desc = description if description is not _UNSET else current["description"]

            row = await conn.fetchrow(
                """
                WITH updated AS (
                    UPDATE sigs SET name = $1, description = $2, updated_at = NOW()
                    WHERE id = $3 AND is_deleted = false
                    RETURNING *
                )
                SELECT u.*, usr.display_name AS creator_display_name
                FROM updated u
                LEFT JOIN users usr ON usr.id = u.created_by
                """,
                new_name,
                new_desc,
                sig_id,
            )
            if not row:
                return None
            logger.info("SIG updated", extra={"sig_id": str(sig_id)})
            result = row_to_sig(dict(row), dict(row).get("creator_display_name"))
    await invalidate_org_chart_cache()
    return result


async def soft_delete_sig(sig_id: uuid.UUID) -> bool:
    deleted = await sig_repo.soft_delete(sig_id)
    if deleted:
        logger.info("SIG soft-deleted", extra={"sig_id": str(sig_id)})
        await invalidate_org_chart_cache()
    return deleted


async def remove_member(
    sig_id: uuid.UUID, user_id: str, *, caller_id: str, caller_role: str
) -> bool:
    """Remove a member from a SIG. Prevents removing the last admin.

    Authorization is checked inside the transaction to prevent TOCTOU races.
    """
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)
    caller_uuid = uuid.UUID(caller_id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Authorize caller inside the transaction
            is_global_admin = caller_role in ("SUPER_ADMIN", "ADMIN")
            if not is_global_admin:
                caller_sig_role = await sig_repo.get_member_role_in_conn(sig_id, caller_uuid, conn)
                if caller_sig_role != "ADMIN":
                    raise PermissionError("Not authorized.")

            member_role = await sig_repo.get_member_role_in_conn(sig_id, user_uuid, conn)
            if not member_role:
                return False

            if member_role == "ADMIN":
                admin_count = await sig_repo.count_admins(sig_id, conn)
                if admin_count <= 1:
                    raise ValueError("Cannot remove: this user is the last admin of the SIG.")

            deleted = await sig_repo.delete_member(sig_id, user_uuid, conn)
            if deleted:
                logger.info(
                    "SIG member removed",
                    extra={"sig_id": str(sig_id), "user_id": user_id},
                )
    if deleted:
        await invalidate_org_chart_cache()
    return deleted


async def leave_sig(sig_id: uuid.UUID, user_id: str) -> bool:
    """Leave a SIG. Validates user is not the last ADMIN."""
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            member_role = await sig_repo.get_member_role_in_conn(sig_id, user_uuid, conn)
            if not member_role:
                return False

            if member_role == "ADMIN":
                admin_count = await sig_repo.count_admins(sig_id, conn)
                if admin_count <= 1:
                    raise ValueError("Cannot leave: you are the last admin of this SIG.")

            deleted = await sig_repo.delete_member(sig_id, user_uuid, conn)
            if deleted:
                logger.info("User left SIG", extra={"sig_id": str(sig_id), "user_id": user_id})
    if deleted:
        await invalidate_org_chart_cache()
    return deleted


async def join_sig(sig_id: uuid.UUID, user_id: str) -> dict:
    """User self-enrolls as MEMBER in a SIG."""
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check inside transaction to prevent TOCTOU race
            existing_role = await sig_repo.get_member_role_in_conn(sig_id, user_uuid, conn)
            if existing_role:
                raise ValueError("Already a member of this SIG.")
            row = await sig_repo.join_member(sig_id, user_uuid, conn)
            if row is None:
                raise ValueError("SIG not found.")
            logger.info("User joined SIG", extra={"sig_id": str(sig_id), "user_id": user_id})
            result = await async_row_to_member(row)
    await invalidate_org_chart_cache()
    return result


async def list_my_sigs(user_id: str) -> list[dict]:
    rows = await sig_repo.find_by_user(uuid.UUID(user_id))
    result = []
    for r in rows:
        sig = row_to_sig(r, r.get("creator_display_name"))
        sig["my_role"] = r["my_role"]
        result.append(sig)
    return result


async def get_member_role(sig_id: uuid.UUID, user_id: str) -> str | None:
    """Check if user is a member of the SIG and return their role."""
    return await sig_repo.get_member_role(sig_id, uuid.UUID(user_id))


async def demote_sub_admin(
    sig_id: uuid.UUID, user_id: str, *, caller_id: str, caller_role: str
) -> dict:
    """Demote a SUB_ADMIN back to MEMBER. Authorization checked inside transaction."""
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)
    caller_uuid = uuid.UUID(caller_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Authorize caller inside the transaction
            is_global_admin = caller_role in ("SUPER_ADMIN", "ADMIN")
            if not is_global_admin:
                caller_sig_role = await sig_repo.get_member_role_in_conn(sig_id, caller_uuid, conn)
                if caller_sig_role != "ADMIN":
                    raise PermissionError("Not authorized.")

            current_role = await sig_repo.get_member_role_in_conn(sig_id, user_uuid, conn)
            if not current_role:
                raise ValueError("User is not a member of this SIG.")
            if current_role == "ADMIN":
                raise ValueError("Cannot demote the SIG owner/creator.")
            if current_role != "SUB_ADMIN":
                raise ValueError("User is not a sub-admin.")

            row = await sig_repo.update_member_role_in_conn(sig_id, user_uuid, "MEMBER", conn)
            if row is None:
                raise ValueError("SIG not found.")

    logger.info("Sub-admin demoted", extra={"sig_id": str(sig_id), "user_id": user_id})
    await emit("sig.role_changed", user_id=user_id, sig_id=str(sig_id), new_role="MEMBER")
    await invalidate_org_chart_cache()
    return await async_row_to_member(row)


async def assign_sub_admin(
    sig_id: uuid.UUID, user_id: str, *, caller_id: str, caller_role: str
) -> dict:
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)
    caller_uuid = uuid.UUID(caller_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Authorize caller inside the transaction
            is_global_admin = caller_role in ("SUPER_ADMIN", "ADMIN")
            if not is_global_admin:
                caller_sig_role = await sig_repo.get_member_role_in_conn(sig_id, caller_uuid, conn)
                if caller_sig_role != "ADMIN":
                    raise PermissionError("Not authorized.")

            # Check if target user is currently an ADMIN — prevent orphaning SIG
            current_role = await sig_repo.get_member_role_in_conn(sig_id, user_uuid, conn)
            if not current_role:
                raise ValueError(
                    "User must be a member of this SIG before being assigned as sub-admin."
                )
            if current_role == "ADMIN":
                admin_count = await sig_repo.count_admins(sig_id, conn)
                if admin_count <= 1:
                    raise ValueError("Cannot demote: this user is the last admin of the SIG.")

            row = await sig_repo.update_member_role_in_conn(sig_id, user_uuid, "SUB_ADMIN", conn)
            if row is None:
                raise ValueError("SIG not found.")

    logger.info("Sub-admin assigned", extra={"sig_id": str(sig_id), "user_id": user_id})
    await emit("sig.role_changed", user_id=user_id, sig_id=str(sig_id), new_role="SUB_ADMIN")
    await invalidate_org_chart_cache()
    return await async_row_to_member(row)


async def list_sig_members(
    sig_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    rows, total = await sig_repo.find_members(sig_id, offset, limit)
    members = list(await asyncio.gather(*[async_row_to_member(r) for r in rows]))
    return members, total
