import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_role
from app.schemas.post import PostListResponse, PostResponse
from app.schemas.sig import (
    SigCreateRequest,
    SigListResponse,
    SigMemberListResponse,
    SigMemberResponse,
    SigResponse,
    SubAdminAssignRequest,
)
from app.services.post import list_posts
from app.services.sig import (
    assign_sub_admin,
    create_sig,
    get_sig_by_id,
    list_sig_members,
    list_sigs,
)

router = APIRouter(prefix="/sigs", tags=["sigs"])


@router.get("", response_model=SigListResponse)
async def get_sigs(
    offset: int = 0,
    limit: int = 50,
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
async def get_sig(sig_id: uuid.UUID) -> SigResponse:
    sig = await get_sig_by_id(sig_id)
    if sig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIG not found.")
    return SigResponse(**sig)


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
    offset: int = 0,
    limit: int = 50,
) -> SigMemberListResponse:
    members, total = await list_sig_members(sig_id, offset=offset, limit=limit)
    return SigMemberListResponse(
        members=[SigMemberResponse(**m) for m in members],
        total=total,
    )


@router.get("/{sig_id}/posts", response_model=PostListResponse)
async def get_sig_posts(
    sig_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> PostListResponse:
    posts, total, total_pages = await list_posts(page=page, page_size=page_size, sig_id=str(sig_id))
    return PostListResponse(
        posts=[PostResponse(**p) for p in posts],
        total=total,
        current_page=page,
        total_pages=total_pages,
    )
