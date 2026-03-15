"""Shared converter utilities to avoid duplication across converters."""

import json
from typing import Any

from app.converters.user_converter import async_resolve_avatar_url, resolve_avatar_url


async def async_build_author(row: dict) -> dict:
    """Async version of build_author — does not block the event loop."""
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
