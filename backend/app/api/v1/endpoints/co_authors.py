import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.constants import RATE_LIMIT_CO_AUTHOR_INVITE
from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.schemas.co_author import (
    CoAuthorInviteRequest,
    CoAuthorListResponse,
    CoAuthorResponse,
    ExternalCoAuthorRequest,
)
from app.services.co_author import (
    add_external_co_author,
    invite_co_author,
    list_co_authored_posts,
    list_co_authors,
    remove_co_author,
)

router = APIRouter(prefix="/co-authors", tags=["co-authors"])


@router.get("/my-posts")
async def list_my_co_authored_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """List posts where the current user is an accepted co-author."""
    posts, total = await list_co_authored_posts(
        user_id=current_user["sub"],
        page=page,
        page_size=page_size,
    )
    return {"posts": posts, "total": total}


@router.get("/user/{user_id}/posts")
async def list_user_co_authored_posts(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List posts where a specific user is an accepted co-author."""
    posts, total = await list_co_authored_posts(
        user_id=str(user_id),
        page=page,
        page_size=page_size,
    )
    return {"posts": posts, "total": total}


@router.post(
    "/posts/{post_id}/invite",
    response_model=CoAuthorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_co_author_endpoint(
    post_id: uuid.UUID,
    req: CoAuthorInviteRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CoAuthorResponse:
    """Invite a platform user as co-author."""
    if not await check_rate_limit(
        f"rl:co_author_invite:{current_user['sub']}", *RATE_LIMIT_CO_AUTHOR_INVITE
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    result = await invite_co_author(
        post_id=post_id,
        user_id=current_user["sub"],
        target_user_id=req.user_id,
        display_name=req.display_name,
    )
    return CoAuthorResponse(**result)


@router.post(
    "/posts/{post_id}/external",
    response_model=CoAuthorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_external_co_author_endpoint(
    post_id: uuid.UUID,
    req: ExternalCoAuthorRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CoAuthorResponse:
    """Add an external (non-platform) co-author."""
    result = await add_external_co_author(
        post_id=post_id,
        user_id=current_user["sub"],
        display_name=req.display_name,
        affiliation=req.affiliation,
        orcid=req.orcid,
    )
    return CoAuthorResponse(**result)


@router.get("/posts/{post_id}", response_model=CoAuthorListResponse)
async def list_co_authors_endpoint(
    post_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> CoAuthorListResponse:
    """List accepted co-authors for a post."""
    result = await list_co_authors(post_id=post_id)
    return CoAuthorListResponse(co_authors=[CoAuthorResponse(**r) for r in result])


@router.delete(
    "/posts/{post_id}/{co_author_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_co_author_endpoint(
    post_id: uuid.UUID,
    co_author_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> None:
    """Remove a co-author from a post."""
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    await remove_co_author(
        post_id=post_id,
        co_author_id=co_author_id,
        user_id=current_user["sub"],
        is_admin=is_admin,
    )
