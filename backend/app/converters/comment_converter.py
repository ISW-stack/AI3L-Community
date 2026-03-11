from app.converters.shared import build_author, safe_json_parse


def row_to_comment(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "content": row["content"],
        "author": build_author(row),
        "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
        "mentions": row.get("mentions"),
        "reactions": safe_json_parse(row.get("reactions")),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
