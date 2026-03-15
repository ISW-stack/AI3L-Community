from app.converters.user_converter import async_resolve_avatar_url, resolve_avatar_url


async def async_row_to_notification(row: dict) -> dict:
    """Async version of row_to_notification — does not block the event loop."""
    result: dict = {
        "id": str(row["id"]),
        "action_type": row["action_type"],
        "entity_type": row.get("entity_type"),
        "entity_id": str(row["entity_id"]) if row.get("entity_id") else None,
        "message": row["message"],
        "is_read": row["is_read"],
        "created_at": row["created_at"].isoformat(),
    }
    if row.get("trigger_user_id") and row.get("trigger_display_name") is not None:
        result["trigger_user"] = {
            "id": str(row["trigger_user_id"]),
            "display_name": row["trigger_display_name"],
            "avatar_url": await async_resolve_avatar_url(row.get("trigger_avatar_url")),
        }
    else:
        result["trigger_user"] = None
    return result


def row_to_notification(row: dict) -> dict:
    result: dict = {
        "id": str(row["id"]),
        "action_type": row["action_type"],
        "entity_type": row.get("entity_type"),
        "entity_id": str(row["entity_id"]) if row.get("entity_id") else None,
        "message": row["message"],
        "is_read": row["is_read"],
        "created_at": row["created_at"].isoformat(),
    }
    if row.get("trigger_user_id") and row.get("trigger_display_name") is not None:
        result["trigger_user"] = {
            "id": str(row["trigger_user_id"]),
            "display_name": row["trigger_display_name"],
            "avatar_url": resolve_avatar_url(row.get("trigger_avatar_url")),
        }
    else:
        result["trigger_user"] = None
    return result
