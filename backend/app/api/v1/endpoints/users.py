import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.schemas.user import UserResponse, UserUpdateRequest
from app.services.user import get_user_by_id, update_user_profile

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)) -> UserResponse:
    user = await get_user_by_id(uuid.UUID(current_user["sub"]))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return UserResponse(
        id=str(user["id"]),
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        avatar_url=user.get("avatar_url"),
        orcid=user.get("orcid"),
        affiliation=user.get("affiliation"),
        bio=user.get("bio"),
    )


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    req: UserUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    user = await update_user_profile(
        user_id=uuid.UUID(current_user["sub"]),
        display_name=req.display_name,
        bio=req.bio,
        affiliation=req.affiliation,
        orcid=req.orcid,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return UserResponse(
        id=str(user["id"]),
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        avatar_url=user.get("avatar_url"),
        orcid=user.get("orcid"),
        affiliation=user.get("affiliation"),
        bio=user.get("bio"),
    )
