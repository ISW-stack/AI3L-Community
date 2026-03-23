from app.converters.shared import (
    async_build_author,
    build_author,
    reactions_to_counts,
    safe_json_parse,
)


async def async_row_to_post(row: dict) -> dict:
    """Async version of row_to_post — does not block the event loop."""
    last_comment_at = row.get("last_comment_at")
    best_answer_id = row.get("best_answer_id")
    raw_reactions = safe_json_parse(row.get("reactions"))
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "content": row["content"],
        "author": await async_build_author(row),
        "category_id": str(row["category_id"]) if row.get("category_id") else None,
        "category_name": row.get("category_name"),
        "sig_id": str(row["sig_id"]) if row.get("sig_id") else None,
        "sig_name": row.get("sig_name"),
        "keywords": row.get("keywords"),
        "allow_comments": row["allow_comments"],
        "version": row["version"],
        "comment_count": row["comment_count"],
        "is_pinned": row.get("is_pinned", False),
        "view_count": row.get("view_count", 0),
        "reaction_counts": reactions_to_counts(row.get("reactions")),
        "user_reactions": None,
        "_raw_reactions": raw_reactions,
        "last_comment_at": last_comment_at.isoformat() if last_comment_at else None,
        "type": row.get("type", "post"),
        "citation_count": row.get("citation_count", 0),
        "answer_count": row.get("answer_count", 0),
        "best_answer_id": str(best_answer_id) if best_answer_id else None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def row_to_post(row: dict) -> dict:
    last_comment_at = row.get("last_comment_at")
    best_answer_id = row.get("best_answer_id")
    raw_reactions = safe_json_parse(row.get("reactions"))
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "content": row["content"],
        "author": build_author(row),
        "category_id": str(row["category_id"]) if row.get("category_id") else None,
        "category_name": row.get("category_name"),
        "sig_id": str(row["sig_id"]) if row.get("sig_id") else None,
        "sig_name": row.get("sig_name"),
        "keywords": row.get("keywords"),
        "allow_comments": row["allow_comments"],
        "version": row["version"],
        "comment_count": row["comment_count"],
        "is_pinned": row.get("is_pinned", False),
        "view_count": row.get("view_count", 0),
        "reaction_counts": reactions_to_counts(row.get("reactions")),
        "user_reactions": None,
        "_raw_reactions": raw_reactions,
        "last_comment_at": last_comment_at.isoformat() if last_comment_at else None,
        "type": row.get("type", "post"),
        "citation_count": row.get("citation_count", 0),
        "answer_count": row.get("answer_count", 0),
        "best_answer_id": str(best_answer_id) if best_answer_id else None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def row_to_history(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "version": row["version"],
        "title": row["title"],
        "content": row["content"],
        "edited_at": row["edited_at"].isoformat(),
    }
