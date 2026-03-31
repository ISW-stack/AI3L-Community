from app.converters.shared import (
    async_build_author,
    build_author,
    reactions_to_counts,
    safe_json_parse,
)


async def async_row_to_event(row: dict) -> dict:
    """Async version of row_to_event — does not block the event loop."""
    raw_reactions = safe_json_parse(row.get("reactions"))
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "content": row["content"],
        "author": await async_build_author(row),
        "sig_id": str(row["sig_id"]) if row.get("sig_id") else None,
        "sig_name": row.get("sig_name"),
        "visibility": row["visibility"],
        "allow_comments": row["allow_comments"],
        "comment_count": row.get("comment_count", 0),
        "reaction_counts": reactions_to_counts(row.get("reactions")),
        "user_reactions": None,
        "_raw_reactions": raw_reactions,
        "version": row["version"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def row_to_event(row: dict) -> dict:
    raw_reactions = safe_json_parse(row.get("reactions"))
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "content": row["content"],
        "author": build_author(row),
        "sig_id": str(row["sig_id"]) if row.get("sig_id") else None,
        "sig_name": row.get("sig_name"),
        "visibility": row["visibility"],
        "allow_comments": row["allow_comments"],
        "comment_count": row.get("comment_count", 0),
        "reaction_counts": reactions_to_counts(row.get("reactions")),
        "user_reactions": None,
        "_raw_reactions": raw_reactions,
        "version": row["version"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
