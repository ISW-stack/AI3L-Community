from app.converters.shared import (
    async_build_author,
    build_author,
    reactions_to_counts,
    safe_json_parse,
)


async def async_row_to_comment(row: dict) -> dict:
    """Async version of row_to_comment — does not block the event loop."""
    raw_reactions = safe_json_parse(row.get("reactions"))
    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "content": row["content"],
        "author": await async_build_author(row),
        "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
        "mentions": row.get("mentions"),
        "reaction_counts": reactions_to_counts(row.get("reactions")),
        "user_reactions": None,
        "_raw_reactions": raw_reactions,
        "vote_score": row.get("vote_score", 0),
        "is_best_answer": row.get("is_best_answer", False),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def row_to_comment(row: dict) -> dict:
    raw_reactions = safe_json_parse(row.get("reactions"))
    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "content": row["content"],
        "author": build_author(row),
        "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
        "mentions": row.get("mentions"),
        "reaction_counts": reactions_to_counts(row.get("reactions")),
        "user_reactions": None,
        "_raw_reactions": raw_reactions,
        "vote_score": row.get("vote_score", 0),
        "is_best_answer": row.get("is_best_answer", False),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
