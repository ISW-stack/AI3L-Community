from app.converters.user_converter import resolve_avatar_url


def _build_author_dict(row: dict) -> dict:
    return {
        "id": str(row["author_id"]),
        "username": row["author_username"],
        "display_name": row["author_display_name"],
        "avatar_url": resolve_avatar_url(row.get("author_avatar_url")),
    }


def row_to_post(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "content": row["content"],
        "author": _build_author_dict(row),
        "category_id": str(row["category_id"]) if row.get("category_id") else None,
        "category_name": row.get("category_name"),
        "keywords": row.get("keywords"),
        "allow_comments": row["allow_comments"],
        "version": row["version"],
        "comment_count": row["comment_count"],
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
