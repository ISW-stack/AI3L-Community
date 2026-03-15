"""Service for friend recommendations."""

import json
import uuid

from app.converters.user_converter import resolve_avatar_url
from app.core.database import get_pool
from app.repositories import recommendation_repo


async def get_recommendations(user_id: str) -> dict:
    """Get precomputed recommendations for the current user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await recommendation_repo.find_recommendations(conn, uuid.UUID(user_id))

    return {
        "recommendations": [
            {
                "id": str(row["id"]),
                "user_id": str(row["recommended_user_id"]),
                "display_name": row["display_name"],
                "username": row["username"],
                "avatar_url": resolve_avatar_url(row.get("avatar_url")),
                "affiliation": row.get("affiliation"),
                "score": row["score"],
                "reasons": (
                    row["reasons"]
                    if isinstance(row["reasons"], list)
                    else json.loads(row["reasons"])
                ),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]
    }


async def dismiss_recommendation(user_id: str, dismissed_user_id: str) -> dict:
    """Dismiss a recommendation."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await recommendation_repo.dismiss_recommendation(
            conn, uuid.UUID(user_id), uuid.UUID(dismissed_user_id)
        )
    return {"message": "Recommendation dismissed"}
