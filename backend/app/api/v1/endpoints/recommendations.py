"""Friend recommendation endpoints."""

from fastapi import APIRouter, Depends

from app.core.constants import RATE_LIMIT_SOCIAL
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.schemas.recommendation import DismissRequest, RecommendationsListResponse
from app.services import recommendation as recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/friends", response_model=RecommendationsListResponse)
async def get_friend_recommendations(
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> RecommendationsListResponse:
    """Get precomputed friend recommendations."""
    result = await recommendation_service.get_recommendations(current_user["sub"])
    return RecommendationsListResponse(**result)


@router.post("/friends/dismiss")
async def dismiss_friend_recommendation(
    body: DismissRequest,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> dict:
    """Dismiss a friend recommendation."""
    if not await check_rate_limit(f"rl:social:{current_user['sub']}", *RATE_LIMIT_SOCIAL):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    return await recommendation_service.dismiss_recommendation(current_user["sub"], body.user_id)
