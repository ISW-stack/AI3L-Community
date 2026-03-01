import uuid

from loguru import logger

from app.core.database import get_pool


async def create_sig(name: str, description: str | None, creator_id: str) -> dict:
    pool = get_pool()
    sig_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_uuid = uuid.UUID(creator_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO sigs (id, name, description, created_by, member_count)
                VALUES ($1, $2, $3, $4, 1)
                RETURNING *
                """,
                sig_id,
                name,
                description,
                creator_uuid,
            )

            # Auto-add creator as ADMIN member
            await conn.execute(
                """
                INSERT INTO sig_members (id, sig_id, user_id, role)
                VALUES ($1, $2, $3, 'ADMIN')
                """,
                member_id,
                sig_id,
                creator_uuid,
            )

            creator = await conn.fetchrow(
                "SELECT display_name FROM users WHERE id = $1",
                creator_uuid,
            )

            logger.info("SIG created", extra={"sig_id": str(sig_id), "name": name})
            return _row_to_sig(dict(row), creator["display_name"] if creator else None)


async def list_sigs(offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM sigs WHERE is_deleted = false",
        )
        rows = await conn.fetch(
            """
            SELECT s.*, u.display_name AS creator_display_name
            FROM sigs s
            LEFT JOIN users u ON s.created_by = u.id
            WHERE s.is_deleted = false
            ORDER BY s.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [_row_to_sig(dict(r), r.get("creator_display_name")) for r in rows], total


async def get_sig_by_id(sig_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.*, u.display_name AS creator_display_name
            FROM sigs s
            LEFT JOIN users u ON s.created_by = u.id
            WHERE s.id = $1 AND s.is_deleted = false
            """,
            sig_id,
        )
        if not row:
            return None
        return _row_to_sig(dict(row), row.get("creator_display_name"))


async def update_sig(sig_id: uuid.UUID, name: str | None = None, description: str | None = None) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        current = await conn.fetchrow(
            "SELECT * FROM sigs WHERE id = $1 AND is_deleted = false",
            sig_id,
        )
        if not current:
            return None

        new_name = name if name is not None else current["name"]
        new_desc = description if description is not None else current["description"]

        row = await conn.fetchrow(
            """
            UPDATE sigs SET name = $1, description = $2, updated_at = NOW()
            WHERE id = $3 AND is_deleted = false
            RETURNING *
            """,
            new_name,
            new_desc,
            sig_id,
        )
        if not row:
            return None

        creator = await conn.fetchrow(
            "SELECT display_name FROM users WHERE id = $1",
            row["created_by"],
        )
        logger.info("SIG updated", extra={"sig_id": str(sig_id)})
        return _row_to_sig(dict(row), creator["display_name"] if creator else None)


async def soft_delete_sig(sig_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute(
                "UPDATE sigs SET is_deleted = true, updated_at = NOW() WHERE id = $1 AND is_deleted = false",
                sig_id,
            )
            if result != "UPDATE 1":
                return False
            # Soft-delete SIG's posts
            await conn.execute(
                "UPDATE posts SET is_deleted = true, updated_at = NOW() WHERE sig_id = $1 AND is_deleted = false",
                sig_id,
            )
            logger.info("SIG soft-deleted", extra={"sig_id": str(sig_id)})
            return True


async def remove_member(sig_id: uuid.UUID, user_id: str) -> bool:
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute(
                "DELETE FROM sig_members WHERE sig_id = $1 AND user_id = $2",
                sig_id,
                user_uuid,
            )
            if result != "DELETE 1":
                return False
            await conn.execute(
                "UPDATE sigs SET member_count = GREATEST(member_count - 1, 0) WHERE id = $1",
                sig_id,
            )
            logger.info("SIG member removed", extra={"sig_id": str(sig_id), "user_id": user_id})
            return True


async def leave_sig(sig_id: uuid.UUID, user_id: str) -> bool:
    """Leave a SIG. Validates user is not the last ADMIN."""
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            member = await conn.fetchrow(
                "SELECT role FROM sig_members WHERE sig_id = $1 AND user_id = $2",
                sig_id,
                user_uuid,
            )
            if not member:
                return False

            if member["role"] == "ADMIN":
                admin_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM sig_members WHERE sig_id = $1 AND role = 'ADMIN'",
                    sig_id,
                )
                if admin_count <= 1:
                    raise ValueError("Cannot leave: you are the last admin of this SIG.")

            result = await conn.execute(
                "DELETE FROM sig_members WHERE sig_id = $1 AND user_id = $2",
                sig_id,
                user_uuid,
            )
            if result != "DELETE 1":
                return False
            await conn.execute(
                "UPDATE sigs SET member_count = GREATEST(member_count - 1, 0) WHERE id = $1",
                sig_id,
            )
            logger.info("User left SIG", extra={"sig_id": str(sig_id), "user_id": user_id})
            return True


async def get_member_role(sig_id: uuid.UUID, user_id: str) -> str | None:
    """Check if user is a member of the SIG and return their role."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT role FROM sig_members WHERE sig_id = $1 AND user_id = $2",
            sig_id,
            uuid.UUID(user_id),
        )
        return row["role"] if row else None


async def assign_sub_admin(sig_id: uuid.UUID, user_id: str) -> dict:
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)
    member_id = uuid.uuid4()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check SIG exists
            sig = await conn.fetchrow(
                "SELECT id FROM sigs WHERE id = $1 AND is_deleted = false",
                sig_id,
            )
            if not sig:
                raise ValueError("SIG not found.")

            # Upsert member with SUB_ADMIN role
            existing = await conn.fetchrow(
                "SELECT id FROM sig_members WHERE sig_id = $1 AND user_id = $2",
                sig_id,
                user_uuid,
            )

            if existing:
                await conn.execute(
                    "UPDATE sig_members SET role = 'SUB_ADMIN', updated_at = NOW() WHERE id = $1",
                    existing["id"],
                )
            else:
                await conn.execute(
                    "INSERT INTO sig_members (id, sig_id, user_id, role) VALUES ($1, $2, $3, 'SUB_ADMIN')",
                    member_id,
                    sig_id,
                    user_uuid,
                )
                await conn.execute(
                    "UPDATE sigs SET member_count = member_count + 1 WHERE id = $1",
                    sig_id,
                )

            row = await conn.fetchrow(
                """
                SELECT sm.*, u.display_name, u.username
                FROM sig_members sm
                JOIN users u ON sm.user_id = u.id
                WHERE sm.sig_id = $1 AND sm.user_id = $2
                """,
                sig_id,
                user_uuid,
            )
            logger.info("Sub-admin assigned", extra={"sig_id": str(sig_id), "user_id": user_id})
            return _row_to_member(dict(row))


async def list_sig_members(
    sig_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM sig_members WHERE sig_id = $1",
            sig_id,
        )
        rows = await conn.fetch(
            """
            SELECT sm.*, u.display_name, u.username
            FROM sig_members sm
            JOIN users u ON sm.user_id = u.id
            WHERE sm.sig_id = $1
            ORDER BY sm.created_at ASC
            LIMIT $2 OFFSET $3
            """,
            sig_id,
            limit,
            offset,
        )
        return [_row_to_member(dict(r)) for r in rows], total


def _row_to_sig(row: dict, creator_display_name: str | None = None) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row.get("description"),
        "created_by": str(row["created_by"]),
        "creator_display_name": creator_display_name,
        "member_count": row["member_count"],
        "created_at": row["created_at"].isoformat(),
    }


def _row_to_member(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "sig_id": str(row["sig_id"]),
        "user_id": str(row["user_id"]),
        "role": row["role"],
        "display_name": row["display_name"],
        "username": row["username"],
        "created_at": row["created_at"].isoformat(),
    }
