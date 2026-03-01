import json


def row_to_comment(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "content": row["content"],
        "author": {
            "id": str(row["author_id"]),
            "username": row["author_username"],
            "display_name": row["author_display_name"],
            "avatar_url": row.get("author_avatar_url"),
        },
        "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
        "mentions": row.get("mentions"),
        "reactions": (
            json.loads(row["reactions"])
            if isinstance(row.get("reactions"), str)
            else row.get("reactions")
        ),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
