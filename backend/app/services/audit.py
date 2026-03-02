import uuid

from loguru import logger

from app.repositories import audit_repo


async def log_action(
    user_id: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert an audit log record (best-effort)."""
    try:
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, AttributeError):
            logger.warning(
                "Invalid user_id for audit log", extra={"user_id": user_id, "action": action}
            )
            return

        log_id = uuid.uuid4()
        target_uuid = uuid.UUID(target_id) if target_id else None
        await audit_repo.insert(log_id, user_uuid, action, target_type, target_uuid, ip_address)
    except Exception as e:
        logger.warning("Failed to write audit log", extra={"action": action, "error": str(e)})


async def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    user_id_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[dict], int]:
    """Return paginated audit logs. Optionally filter by user_id and date range."""
    filter_uuid = uuid.UUID(user_id_filter) if user_id_filter else None
    rows, total = await audit_repo.find_many(
        page, page_size, filter_uuid, date_from=date_from, date_to=date_to
    )

    logs = []
    for r in rows:
        logs.append(
            {
                "id": str(r["id"]),
                "user_id": str(r["user_id"]),
                "username": r.get("username"),
                "display_name": r.get("display_name"),
                "action": r["action"],
                "target_type": r["target_type"],
                "target_id": str(r["target_id"]) if r["target_id"] else None,
                "ip_address": r["ip_address"],
                "created_at": r["created_at"].isoformat(),
            }
        )

    return logs, total
