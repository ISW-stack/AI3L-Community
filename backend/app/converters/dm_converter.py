"""Converters for DM conversations and messages."""

from app.converters.user_converter import async_resolve_avatar_url


async def async_row_to_message(row: dict) -> dict:
    """Convert DB row to message response dict.

    Expects sender_display_name and sender_avatar_url from JOIN.
    M-19: Explicitly strip content/attachment fields for recalled messages
    to prevent replication-lag exposure.
    """
    is_recalled = row.get("is_recalled", False)
    return {
        "id": str(row["id"]),
        "conversation_id": str(row["conversation_id"]),
        "sender": {
            "id": str(row["sender_id"]),
            "display_name": row.get("sender_display_name", ""),
            "avatar_url": await async_resolve_avatar_url(row.get("sender_avatar_url")),
        },
        "content": None if is_recalled else row.get("content"),
        "attachment_url": None,  # presigned URL generated in service layer
        "attachment_name": None if is_recalled else row.get("attachment_name"),
        "attachment_size": None if is_recalled else row.get("attachment_size"),
        "attachment_expires_at": (
            None
            if is_recalled
            else (
                row["attachment_expires_at"].isoformat()
                if row.get("attachment_expires_at")
                else None
            )
        ),
        "is_recalled": is_recalled,
        "is_edited": row["is_edited"],
        "read_at": row["read_at"].isoformat() if row.get("read_at") else None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def async_row_to_conversation(row: dict, user_id: str) -> dict:
    """Convert DB row to conversation response dict.

    Expects other_user_id, other_display_name, other_avatar_url from JOIN,
    and last_msg_* prefixed fields from LATERAL join.
    """
    other_user = {
        "id": str(row["other_user_id"]),
        "display_name": row.get("other_display_name", ""),
        "avatar_url": await async_resolve_avatar_url(row.get("other_avatar_url")),
    }

    # Build last_message if present
    last_message = None
    if row.get("last_msg_id") is not None:
        last_message = {
            "id": str(row["last_msg_id"]),
            "conversation_id": str(row["last_msg_conversation_id"]),
            "sender": {
                "id": str(row["last_msg_sender_id"]),
                "display_name": row.get("last_msg_sender_display_name", ""),
                "avatar_url": await async_resolve_avatar_url(row.get("last_msg_sender_avatar_url")),
            },
            "content": row.get("last_msg_content"),
            "attachment_url": None,
            "attachment_name": row.get("last_msg_attachment_name"),
            "attachment_size": row.get("last_msg_attachment_size"),
            "attachment_expires_at": (
                row["last_msg_attachment_expires_at"].isoformat()
                if row.get("last_msg_attachment_expires_at")
                else None
            ),
            "is_recalled": row.get("last_msg_is_recalled", False),
            "is_edited": row.get("last_msg_is_edited", False),
            "read_at": (
                row["last_msg_read_at"].isoformat() if row.get("last_msg_read_at") else None
            ),
            "created_at": row["last_msg_created_at"].isoformat(),
            "updated_at": row["last_msg_updated_at"].isoformat(),
        }

    return {
        "id": str(row["id"]),
        "other_user": other_user,
        "last_message": last_message,
        "unread_count": int(row.get("unread_count", 0)),
        "updated_at": row["updated_at"].isoformat(),
    }
