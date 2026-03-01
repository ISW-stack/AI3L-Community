def row_to_application(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "username": row.get("username"),
        "display_name": row.get("display_name"),
        "description": row["description"],
        "status": row["status"],
        "reviewed_by": str(row["reviewed_by"]) if row.get("reviewed_by") else None,
        "reviewed_at": row["reviewed_at"].isoformat() if row.get("reviewed_at") else None,
        "created_at": row["created_at"].isoformat(),
    }
