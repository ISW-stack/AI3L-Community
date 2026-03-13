import json
from datetime import datetime, timezone
from typing import Any

from app.converters.shared import safe_json_parse


def row_to_form(row: dict, response_count: int = 0) -> dict:
    deadline = row.get("deadline")
    now = datetime.now(timezone.utc)

    is_expired = deadline is not None and deadline < now
    is_full = row.get("max_respondents") is not None and response_count >= row["max_respondents"]
    is_active = not is_expired and not is_full and not row.get("is_deleted", False)

    return {
        "id": str(row["id"]),
        "sig_id": str(row["sig_id"]),
        "title": row["title"],
        "description": row.get("description"),
        "banner_url": row.get("banner_url"),
        "deadline": row["deadline"].isoformat() if row.get("deadline") else None,
        "max_respondents": row.get("max_respondents"),
        "questions": safe_json_parse(row.get("questions")),
        "is_schema_locked": row.get("is_schema_locked", False),
        "allow_non_members": row.get("allow_non_members", False),
        "response_count": response_count,
        "is_active": is_active,
        "created_by": str(row["created_by"]),
        "created_by_name": row.get("creator_display_name") or "Unknown",
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def row_to_form_list_item(row: dict, response_count: int = 0) -> dict:
    """Convert a paginated list row (includes creator_display_name) to a form dict.

    Identical in shape to ``row_to_form`` — provided as a named entry point
    so callers can signal intent and future divergence is easy to add.
    """
    return row_to_form(row, response_count)


def row_to_form_response(row: dict) -> dict:
    """Convert a form_responses JOIN users row to the API response dict.

    Expected row keys: id, form_id, user_id, answers, created_at,
    display_name, username.
    """
    answers: Any = row.get("answers")
    if isinstance(answers, str):
        answers = json.loads(answers)
    return {
        "id": str(row["id"]),
        "form_id": str(row["form_id"]),
        "user_id": str(row["user_id"]),
        "display_name": row.get("display_name"),
        "username": row.get("username"),
        "answers": answers,
        "created_at": row["created_at"].isoformat(),
    }


def row_to_form_response_for_stats(row: dict) -> dict:
    """Convert a raw stats row (id, form_id, user_id, answers, created_at)
    to a plain dict suitable for aggregation in ``get_form_stats``.

    ``answers`` is guaranteed to be a parsed dict (never a raw JSON string).
    """
    answers: Any = row.get("answers")
    if isinstance(answers, str):
        answers = json.loads(answers)
    return {
        "id": str(row["id"]),
        "form_id": str(row["form_id"]),
        "user_id": str(row["user_id"]),
        "answers": answers,
        "created_at": row["created_at"].isoformat(),
    }
