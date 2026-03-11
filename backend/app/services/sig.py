import uuid

from loguru import logger

from app.converters.sig_converter import row_to_member, row_to_sig
from app.core.database import get_pool
from app.repositories import sig_repo


async def create_sig(name: str, description: str | None, creator_id: str) -> dict:
    pool = get_pool()
    sig_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_uuid = uuid.UUID(creator_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await sig_repo.insert(sig_id, name, description, creator_uuid, conn)
            await sig_repo.add_member(member_id, sig_id, creator_uuid, "ADMIN", conn)
            creator_name = await sig_repo.find_creator_display_name(creator_uuid, conn)

            logger.info("SIG created", extra={"sig_id": str(sig_id), "name": name})
            return row_to_sig(row, creator_name)


async def list_sigs(offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    rows, total = await sig_repo.find_many(offset, limit)
    return [row_to_sig(r, r.get("creator_display_name")) for r in rows], total


async def get_sig_by_id(sig_id: uuid.UUID) -> dict | None:
    row = await sig_repo.find_by_id(sig_id)
    if not row:
        return None
    return row_to_sig(row, row.get("creator_display_name"))


async def update_sig(
    sig_id: uuid.UUID, name: str | None = None, description: str | None = None
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
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
            new_name = name if name is not None else current["name"]
            new_desc = description if description is not None else current["description"]

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
            return row_to_sig(dict(row), dict(row).get("creator_display_name"))


async def soft_delete_sig(sig_id: uuid.UUID) -> bool:
    deleted = await sig_repo.soft_delete(sig_id)
    if deleted:
        logger.info("SIG soft-deleted", extra={"sig_id": str(sig_id)})
    return deleted


async def remove_member(sig_id: uuid.UUID, user_id: str) -> bool:
    removed = await sig_repo.remove_member(sig_id, uuid.UUID(user_id))
    if removed:
        logger.info("SIG member removed", extra={"sig_id": str(sig_id), "user_id": user_id})
    return removed


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
            return row_to_member(row)


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


async def demote_sub_admin(sig_id: uuid.UUID, user_id: str) -> dict:
    """Demote a SUB_ADMIN back to MEMBER. Only SIG owners or platform admins may call this."""
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
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
    return row_to_member(row)


async def assign_sub_admin(sig_id: uuid.UUID, user_id: str) -> dict:
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
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
    return row_to_member(row)


async def list_sig_members(
    sig_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    rows, total = await sig_repo.find_members(sig_id, offset, limit)
    return [row_to_member(r) for r in rows], total
