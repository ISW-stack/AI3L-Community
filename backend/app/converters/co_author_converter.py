"""Converter for post_co_authors rows to response dicts."""

from app.converters.user_converter import async_resolve_avatar_url


async def to_co_author_response(row: dict) -> dict:
    """Convert a co-author row (with user JOIN) to CoAuthorResponse dict."""
    # Use user's display_name if available, else the stored display_name
    display_name = row.get("user_display_name") or row.get("display_name", "")
    avatar_url = await async_resolve_avatar_url(row.get("user_avatar_url"))

    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "user_id": str(row["user_id"]) if row.get("user_id") else None,
        "display_name": display_name,
        "affiliation": row.get("affiliation"),
        "orcid": row.get("orcid"),
        "is_external": row.get("is_external", False),
        "status": row["status"],
        "avatar_url": avatar_url,
        "invited_at": row["invited_at"].isoformat() if row.get("invited_at") else None,
        "responded_at": row["responded_at"].isoformat() if row.get("responded_at") else None,
    }


async def to_co_author_invitation_response(row: dict) -> dict:
    """Convert a pending invitation row to CoAuthorInvitationResponse dict."""
    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "post_title": row.get("post_title", ""),
        "invited_by_name": row.get("invited_by_name", ""),
        "invited_at": row["invited_at"].isoformat() if row.get("invited_at") else None,
        "status": row["status"],
    }
