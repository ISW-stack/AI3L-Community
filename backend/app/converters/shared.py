"""Shared converter utilities to avoid duplication across converters."""

import json
from typing import Any

from app.converters.user_converter import async_resolve_avatar_url, resolve_avatar_url


async def async_build_author(row: dict) -> dict:
    """Async version of build_author — does not block the event loop.

    NOTE on banned users: Banned users' historical content (posts, comments)
    remains visible under their original display_name. The post query does not
    JOIN user ban status, so masking would require a repository-level change.
    Current policy: content is preserved; full removal of personal data uses
    the GDPR anonymize_user flow (which replaces display_name with
    "Deleted User" and clears avatar).
    """
    return {
        "id": str(row["author_id"]),
        "username": row["author_username"],
        "display_name": row["author_display_name"],
        "avatar_url": await async_resolve_avatar_url(row.get("author_avatar_url")),
    }


def build_author(row: dict) -> dict:
    """Build a standard author response dict from a joined query row."""
    return {
        "id": str(row["author_id"]),
        "username": row["author_username"],
        "display_name": row["author_display_name"],
        "avatar_url": resolve_avatar_url(row.get("author_avatar_url")),
    }


def safe_json_parse(value: Any) -> Any:
    """Parse JSON string if needed, otherwise return as-is.

    Returns None on malformed JSON rather than crashing the converter.
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def reactions_to_counts(raw: Any) -> dict[str, int] | None:
    """Convert reactions {type: [user_ids]} to {type: count}."""
    parsed = safe_json_parse(raw)
    if not parsed or not isinstance(parsed, dict):
        return None
    return {k: len(v) for k, v in parsed.items() if isinstance(v, list) and v}


def fill_user_reactions(item: dict, viewer_id: str | None) -> dict:
    """Set user_reactions on an item dict based on raw reactions and viewer_id."""
    if not viewer_id:
        return item
    raw = item.get("_raw_reactions")
    if not raw or not isinstance(raw, dict):
        return item
    item["user_reactions"] = [k for k, v in raw.items() if isinstance(v, list) and viewer_id in v]
    return item
