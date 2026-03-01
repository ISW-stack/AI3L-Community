import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user, require_role
from app.schemas.post import PostListResponse, PostResponse
from app.schemas.auth import MessageResponse
from app.schemas.sig import (
    SigCreateRequest,
    SigListResponse,
    SigMemberListResponse,
    SigMemberResponse,
    SigResponse,
    SigUpdateRequest,
    SubAdminAssignRequest,
)
from app.services.post import list_posts
from app.services.sig import (
    assign_sub_admin,
    create_sig,
    get_member_role,
    get_sig_by_id,
    leave_sig,
    list_sig_members,
    list_sigs,
    remove_member,
    soft_delete_sig,
    update_sig,
)

router = APIRouter(prefix="/sigs", tags=["sigs"])


@router.get("", response_model=SigListResponse)
async def get_sigs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> SigListResponse:
    sigs, total = await list_sigs(offset=offset, limit=limit)
    return SigListResponse(
        sigs=[SigResponse(**s) for s in sigs],
        total=total,
    )


@router.post("", response_model=SigResponse, status_code=status.HTTP_201_CREATED)
async def create_new_sig(
    req: SigCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> SigResponse:
    try:
        sig = await create_sig(req.name, req.description, current_user["sub"])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return SigResponse(**sig)


@router.get("/{sig_id}", response_model=SigResponse)
async def get_sig(
    sig_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> SigResponse:
    sig = await get_sig_by_id(sig_id)
    if sig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIG not found.")
    return SigResponse(**sig)


@router.put("/{sig_id}", response_model=SigResponse)
async def update_existing_sig(
    sig_id: uuid.UUID,
    req: SigUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> SigResponse:
    # Allow SUPER_ADMIN, ADMIN, or SIG ADMIN
    is_global_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    if not is_global_admin:
        sig_role = await get_member_role(sig_id, current_user["sub"])
        if sig_role != "ADMIN":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

    sig = await update_sig(sig_id, name=req.name, description=req.description)
    if sig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIG not found.")
    return SigResponse(**sig)


@router.delete("/{sig_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sig(
    sig_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> None:
    deleted = await soft_delete_sig(sig_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIG not found.")


@router.delete("/{sig_id}/members/me", response_model=MessageResponse)
async def leave_sig_endpoint(
    sig_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    try:
        left = await leave_sig(sig_id, current_user["sub"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not left:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not a member of this SIG."
        )
    return MessageResponse(message="Left SIG successfully.")


@router.delete("/{sig_id}/members/{user_id}", response_model=MessageResponse)
async def remove_sig_member(
    sig_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    # Allow SUPER_ADMIN, ADMIN, or SIG ADMIN
    is_global_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    if not is_global_admin:
        sig_role = await get_member_role(sig_id, current_user["sub"])
        if sig_role != "ADMIN":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

    # Prevent removing self via this endpoint
    if str(user_id) == current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the leave endpoint to remove yourself.",
        )

    removed = await remove_member(sig_id, str(user_id))
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    return MessageResponse(message="Member removed.")


@router.post("/{sig_id}/sub-admin", response_model=SigMemberResponse)
async def assign_sig_sub_admin(
    sig_id: uuid.UUID,
    req: SubAdminAssignRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> SigMemberResponse:
    try:
        member = await assign_sub_admin(sig_id, req.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return SigMemberResponse(**member)


@router.get("/{sig_id}/members", response_model=SigMemberListResponse)
async def get_sig_members(
    sig_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> SigMemberListResponse:
    members, total = await list_sig_members(sig_id, offset=offset, limit=limit)
    return SigMemberListResponse(
        members=[SigMemberResponse(**m) for m in members],
        total=total,
    )


@router.get("/{sig_id}/posts", response_model=PostListResponse)
async def get_sig_posts(
    sig_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> PostListResponse:
    posts, total, total_pages = await list_posts(page=page, page_size=page_size, sig_id=str(sig_id))
    return PostListResponse(
        posts=[PostResponse(**p) for p in posts],
        total=total,
        current_page=page,
        total_pages=total_pages,
    )
