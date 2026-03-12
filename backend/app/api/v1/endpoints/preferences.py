import uuid

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
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
    data = req.model_dump(exclude_none=True)
    prefs = await update_user_preferences(uuid.UUID(current_user["sub"]), data)
    return UserPreferencesResponse(**prefs)
