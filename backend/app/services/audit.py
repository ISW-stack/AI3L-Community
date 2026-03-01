import math
import uuid

from loguru import logger

from app.core.database import get_pool


async def log_action(
    user_id: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert an audit log record (best-effort)."""
    try:
        # Validate user_id is a valid UUID to avoid asyncpg DataError
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, AttributeError):
            logger.warning("Invalid user_id for audit log", extra={"user_id": user_id, "action": action})
            return

        pool = get_pool()
        log_id = uuid.uuid4()
        target_uuid = uuid.UUID(target_id) if target_id else None
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs (id, user_id, action, target_type, target_id, ip_address)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                log_id,
                user_uuid,
                action,
                target_type,
                target_uuid,
                ip_address,
            )
    except Exception as e:
        logger.warning("Failed to write audit log", extra={"action": action, "error": str(e)})


async def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    user_id_filter: str | None = None,
) -> tuple[list[dict], int]:
    """Return paginated audit logs. Optionally filter by user_id."""
    pool = get_pool()
    offset = (page - 1) * page_size

    where = ""
    params: list = []
    idx = 1

    if user_id_filter:
        where = f"WHERE al.user_id = ${idx}"
        params.append(uuid.UUID(user_id_filter))
        idx += 1

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM audit_logs al {where}",
            *params,
        )

        params.extend([page_size, offset])
        rows = await conn.fetch(
            f"""
            SELECT al.*, u.username, u.display_name
            FROM audit_logs al
            LEFT JOIN users u ON u.id = al.user_id
            {where}
            ORDER BY al.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )

        logs = []
        for r in rows:
            logs.append({
                "id": str(r["id"]),
                "user_id": str(r["user_id"]),
                "username": r.get("username"),
                "display_name": r.get("display_name"),
                "action": r["action"],
                "target_type": r["target_type"],
                "target_id": str(r["target_id"]) if r["target_id"] else None,
                "ip_address": r["ip_address"],
                "created_at": r["created_at"].isoformat(),
            })

        return logs, total
