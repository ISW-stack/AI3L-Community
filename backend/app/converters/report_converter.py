def row_to_report(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "user_id": str(row["user_id"]),
        "reason": row["reason"],
        "status": row["status"],
        "reviewed_by": str(row["reviewed_by"]) if row.get("reviewed_by") else None,
        "reviewed_at": row["reviewed_at"].isoformat() if row.get("reviewed_at") else None,
        "created_at": row["created_at"].isoformat(),
    }
