import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.constants import (
    MAX_PAGE_NUMBER,
    RATE_LIMIT_SIG_CRUD,
    RATE_LIMIT_SIG_JOIN,
    RATE_LIMIT_SIG_MANAGE,
)
from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.file_validation import sanitize_html
from app.core.rate_limit import check_rate_limit
from app.schemas.auth import MessageResponse
from app.schemas.post import PostListResponse
from app.schemas.sig import (
    MySigListResponse,
    MySigResponse,
    SigCreateRequest,
    SigListResponse,
    SigMemberListResponse,
    SigMemberResponse,
    SigMyRoleResponse,
    SigResponse,
    SigUpdateRequest,
    SubAdminAssignRequest,
)
from app.services.post import list_posts
from app.services.sig import (
    assign_sub_admin,
    create_sig,
    demote_sub_admin,
    get_member_role,
    get_sig_by_id,
    join_sig,
    leave_sig,
    list_my_sigs,
    list_sig_members,
    list_sigs,
    remove_member,
    soft_delete_sig,
    update_sig,
)

router = APIRouter(prefix="/sigs", tags=["sigs"])


@router.get("", response_model=SigListResponse)
async def get_sigs(
    response: Response,
    offset: int = Query(0, ge=0, le=MAX_PAGE_NUMBER * 100),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> SigListResponse:
    response.headers["Cache-Control"] = "private, max-age=60"
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
    if not await check_rate_limit(f"rl:sig_crud:{current_user['sub']}", *RATE_LIMIT_SIG_CRUD):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    description = sanitize_html(req.description) if req.description else req.description
    try:
        sig = await create_sig(req.name, description, current_user["sub"])
    except ValueError as e:
        raise AppError(ErrorCode.SYS_409, 409, str(e))
    return SigResponse(**sig)


@router.get("/my", response_model=MySigListResponse)
async def get_my_sigs(
    current_user: dict = Depends(get_current_user),
) -> MySigListResponse:
    sigs = await list_my_sigs(current_user["sub"])
    return MySigListResponse(sigs=[MySigResponse(**s) for s in sigs])


@router.get("/{sig_id}", response_model=SigResponse)
async def get_sig(
    sig_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> SigResponse:
    sig = await get_sig_by_id(sig_id)
    if sig is None:
        raise AppError(ErrorCode.SYS_404, 404, "SIG not found.")
    return SigResponse(**sig)


@router.put("/{sig_id}", response_model=SigResponse)
async def update_existing_sig(
    sig_id: uuid.UUID,
    req: SigUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> SigResponse:
    if not await check_rate_limit(f"rl:sig_crud:{current_user['sub']}", *RATE_LIMIT_SIG_CRUD):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    # Permission check is done inside the service layer transaction to prevent TOCTOU
    description = sanitize_html(req.description) if req.description else req.description
    try:
        sig = await update_sig(
            sig_id,
            name=req.name,
            description=description,
            caller_id=current_user["sub"],
            caller_role=current_user["role"],
        )
    except PermissionError:
        raise AppError(ErrorCode.SYS_403, 403, "Not authorized.")
    if sig is None:
        raise AppError(ErrorCode.SYS_404, 404, "SIG not found.")
    return SigResponse(**sig)


@router.delete("/{sig_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sig(
    sig_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> None:
    if not await check_rate_limit(f"rl:sig_crud:{current_user['sub']}", *RATE_LIMIT_SIG_CRUD):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    deleted = await soft_delete_sig(sig_id)
    if not deleted:
        raise AppError(ErrorCode.SYS_404, 404, "SIG not found.")


@router.get("/{sig_id}/members/me", response_model=SigMyRoleResponse)
async def get_my_sig_membership(
    sig_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> SigMyRoleResponse:
    """Return the current user's membership role in this SIG."""
    role = await get_member_role(sig_id, current_user["sub"])
    if role is None:
        raise AppError(ErrorCode.SYS_404, 404, "Not a member of this SIG.")
    return SigMyRoleResponse(role=role)


@router.post(
    "/{sig_id}/members/me", response_model=SigMemberResponse, status_code=status.HTTP_201_CREATED
)
async def join_sig_endpoint(
    sig_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> SigMemberResponse:
    if not await check_rate_limit(f"rl:sig_join:{current_user['sub']}", *RATE_LIMIT_SIG_JOIN):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    try:
        member = await join_sig(sig_id, current_user["sub"])
    except ValueError as e:
        msg = str(e)
        if "already a member" in msg.lower():
            raise AppError(ErrorCode.SYS_409, 409, msg)
        raise AppError(ErrorCode.SYS_404, 404, msg)
    except PermissionError as e:
        raise AppError(ErrorCode.SYS_403, 403, str(e))
    return SigMemberResponse(**member)


@router.delete("/{sig_id}/members/me", response_model=MessageResponse)
async def leave_sig_endpoint(
    sig_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    if not await check_rate_limit(f"rl:sig_leave:{current_user['sub']}", *RATE_LIMIT_SIG_JOIN):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    try:
        left = await leave_sig(sig_id, current_user["sub"])
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, str(e))
    if not left:
        raise AppError(ErrorCode.SYS_404, 404, "Not a member of this SIG.")
    return MessageResponse(message="Left SIG successfully.")


@router.delete("/{sig_id}/members/{user_id}", response_model=MessageResponse)
async def remove_sig_member(
    sig_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    if not await check_rate_limit(f"rl:sig_manage:{current_user['sub']}", *RATE_LIMIT_SIG_MANAGE):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    # Prevent removing self via this endpoint
    if str(user_id) == current_user["sub"]:
        raise AppError(ErrorCode.SYS_422, 422, "Use the leave endpoint to remove yourself.")

    try:
        removed = await remove_member(
            sig_id,
            str(user_id),
            caller_id=current_user["sub"],
            caller_role=current_user["role"],
        )
    except PermissionError:
        raise AppError(ErrorCode.SYS_403, 403, "Not authorized.")
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, str(e))
    if not removed:
        raise AppError(ErrorCode.SYS_404, 404, "Member not found.")
    return MessageResponse(message="Member removed.")


@router.post("/{sig_id}/sub-admin", response_model=SigMemberResponse)
async def assign_sig_sub_admin(
    sig_id: uuid.UUID,
    req: SubAdminAssignRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> SigMemberResponse:
    if not await check_rate_limit(f"rl:sig_manage:{current_user['sub']}", *RATE_LIMIT_SIG_MANAGE):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    try:
        member = await assign_sub_admin(
            sig_id,
            str(req.user_id),
            caller_id=current_user["sub"],
            caller_role=current_user["role"],
        )
    except PermissionError:
        raise AppError(ErrorCode.SYS_403, 403, "Not authorized.")
    except ValueError as e:
        raise AppError(ErrorCode.SYS_404, 404, str(e))
    return SigMemberResponse(**member)


@router.post("/{sig_id}/sub-admin/demote", response_model=SigMemberResponse)
async def demote_sig_sub_admin(
    sig_id: uuid.UUID,
    req: SubAdminAssignRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> SigMemberResponse:
    """Demote a sub-admin back to regular member."""
    if not await check_rate_limit(f"rl:sig_manage:{current_user['sub']}", *RATE_LIMIT_SIG_MANAGE):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    try:
        member = await demote_sub_admin(
            sig_id,
            str(req.user_id),
            caller_id=current_user["sub"],
            caller_role=current_user["role"],
        )
    except PermissionError:
        raise AppError(ErrorCode.SYS_403, 403, "Not authorized.")
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, str(e))
    return SigMemberResponse(**member)


@router.get("/{sig_id}/members", response_model=SigMemberListResponse)
async def get_sig_members(
    sig_id: uuid.UUID,
    offset: int = Query(0, ge=0, le=MAX_PAGE_NUMBER * 100),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> SigMemberListResponse:
    members, total = await list_sig_members(sig_id, offset=offset, limit=limit)
    return SigMemberListResponse(
        members=[SigMemberResponse(**m) for m in members],
        total=total,
    )


@router.get("/{sig_id}/posts", response_model=PostListResponse)
async def get_sig_posts(
    sig_id: uuid.UUID,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> PostListResponse:
    result = await list_posts(
        page=page, page_size=page_size, sig_id=str(sig_id), viewer_id=current_user["sub"]
    )
    return PostListResponse(
        posts=cast(list[Any], result["posts"]),
        total=result["total"],
        page=page,
        total_pages=result["total_pages"],
    )
