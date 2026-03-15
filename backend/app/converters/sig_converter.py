from app.converters.user_converter import async_resolve_avatar_url, resolve_avatar_url


async def async_row_to_member(row: dict) -> dict:
    """Async version of row_to_member — does not block the event loop."""
    return {
        "id": str(row["id"]),
        "sig_id": str(row["sig_id"]),
        "user_id": str(row["user_id"]),
        "role": row["role"],
        "display_name": row["display_name"],
        "username": row["username"],
        "avatar_url": await async_resolve_avatar_url(row.get("avatar_url")),
        "created_at": row["created_at"].isoformat(),
    }


def row_to_sig(row: dict, creator_display_name: str | None = None) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row.get("description"),
        "created_by": str(row["created_by"]),
        "creator_display_name": creator_display_name or row.get("creator_display_name"),
        "member_count": row["member_count"],
        "created_at": row["created_at"].isoformat(),
    }


def row_to_member(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "sig_id": str(row["sig_id"]),
        "user_id": str(row["user_id"]),
        "role": row["role"],
        "display_name": row["display_name"],
        "username": row["username"],
        "avatar_url": resolve_avatar_url(row.get("avatar_url")),
        "created_at": row["created_at"].isoformat(),
    }
