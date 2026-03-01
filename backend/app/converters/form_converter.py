import json
from datetime import datetime, timezone


def row_to_form(row: dict, response_count: int = 0) -> dict:
    deadline = row.get("deadline")
    now = datetime.now(timezone.utc)

    is_expired = deadline is not None and deadline < now
    is_full = (
        row.get("max_respondents") is not None
        and response_count >= row["max_respondents"]
    )
    is_active = not is_expired and not is_full and not row.get("is_deleted", False)

    return {
        "id": str(row["id"]),
        "sig_id": str(row["sig_id"]),
        "title": row["title"],
        "description": row.get("description"),
        "banner_url": row.get("banner_url"),
        "deadline": row["deadline"].isoformat() if row.get("deadline") else None,
        "max_respondents": row.get("max_respondents"),
        "questions": (
            json.loads(row["questions"])
            if isinstance(row["questions"], str)
            else row["questions"]
        ),
        "is_schema_locked": row.get("is_schema_locked", False),
        "response_count": response_count,
        "is_active": is_active,
        "created_by": str(row["created_by"]),
        "created_by_name": row.get("creator_display_name") or "Unknown",
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
