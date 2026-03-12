import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.constants import RATE_LIMIT_PREFERENCES
from app.core.deps import get_current_user
from app.core.rate_limit import check_rate_limit
from app.schemas.preferences import UserPreferencesResponse, UserPreferencesUpdate
from app.services.preferences import get_user_preferences, update_user_preferences

router = APIRouter(prefix="/users/me/preferences", tags=["preferences"])


@router.get("", response_model=UserPreferencesResponse)
async def get_preferences(
    current_user: dict = Depends(get_current_user),
) -> UserPreferencesResponse:
    """Get current user's preferences (returns defaults if none saved)."""
    prefs = await get_user_preferences(uuid.UUID(current_user["sub"]))
    return UserPreferencesResponse(**prefs)


@router.put("", response_model=UserPreferencesResponse)
async def update_preferences(
    req: UserPreferencesUpdate,
    current_user: dict = Depends(get_current_user),
) -> UserPreferencesResponse:
    """Update current user's preferences (partial update via upsert)."""
    if not await check_rate_limit(
        f"rl:preferences:{current_user['sub']}", *RATE_LIMIT_PREFERENCES
    ):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    data = req.model_dump(exclude_none=True)
    prefs = await update_user_preferences(uuid.UUID(current_user["sub"]), data)
    return UserPreferencesResponse(**prefs)
