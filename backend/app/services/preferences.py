import uuid

from app.repositories import preferences_repo

_DEFAULTS = {
    "theme": "light",
    "notify_mentions": True,
    "notify_replies": True,
    "notify_sig_posts": True,
    "dm_friends_only": False,
}


async def get_user_preferences(user_id: uuid.UUID) -> dict:
    """Return user preferences, falling back to defaults if no row exists."""
    row = await preferences_repo.get_preferences(user_id)
    if row is None:
        return dict(_DEFAULTS)
    return row


async def update_user_preferences(user_id: uuid.UUID, data: dict) -> dict:
    """Upsert user preferences with the provided partial data."""
    return await preferences_repo.upsert_preferences(user_id, data)
