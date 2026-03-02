import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode, RateLimitError
from app.core.event_bus import emit
from app.core.file_validation import sanitize_html
from app.schemas.post import (
    PostCreateRequest,
    PostHistoryResponse,
    PostListResponse,
    PostResponse,
    PostSearchRequest,
    PostUpdateRequest,
)
from app.services.post import (
    create_post,
    get_post_by_id,
    get_post_history,
    list_posts,
    search_posts,
    soft_delete_post,
    update_post,
)

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_new_post(
    req: PostCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> PostResponse:
    try:
        post = await create_post(
            user_id=current_user["sub"],
            title=req.title,
            content=sanitize_html(req.content),
            category_id=req.category_id,
            sig_id=req.sig_id,
            keywords=req.keywords,
            allow_comments=req.allow_comments,
        )
    except RateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return PostResponse(**post)


@router.get("", response_model=PostListResponse)
async def get_posts_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: str | None = None,
    author_id: str | None = None,
    sort: str = Query("newest", pattern="^(newest|oldest|most_comments)$"),
    current_user: dict = Depends(get_current_user),
) -> PostListResponse:
    posts, total, total_pages = await list_posts(
        page=page, page_size=page_size, category_id=category_id, author_id=author_id, sort=sort
    )
    return PostListResponse(
        posts=posts,  # type: ignore[arg-type]
        total=total,
        current_page=page,
        total_pages=total_pages,
    )


@router.post("/search", response_model=PostListResponse)
async def search_posts_endpoint(
    req: PostSearchRequest,
    current_user: dict = Depends(get_current_user),
) -> PostListResponse:
    posts, total, total_pages = await search_posts(
        keyword=req.keyword,
        category_id=req.category_id,
        keywords_filter=req.keywords,
        date_from=req.date_from,
        date_to=req.date_to,
        logic=req.logic,
        page=req.page,
        page_size=req.page_size,
    )
    return PostListResponse(
        posts=posts,  # type: ignore[arg-type]
        total=total,
        current_page=req.page,
        total_pages=total_pages,
    )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> PostResponse:
    post = await get_post_by_id(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return PostResponse(**post)


@router.put("/{post_id}", response_model=PostResponse)
async def update_existing_post(
    post_id: uuid.UUID,
    req: PostUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> PostResponse:
    if not any([
        req.title,
        req.content,
        req.category_id is not None,
        req.keywords is not None,
        req.allow_comments is not None,
    ]):
        raise HTTPException(status_code=400, detail="At least one field must be provided.")

    content = sanitize_html(req.content) if req.content else None
    try:
        post = await update_post(
            post_id=post_id,
            user_id=current_user["sub"],
            title=req.title,
            content=content,
            category_id=req.category_id,
            keywords=req.keywords,
            allow_comments=req.allow_comments,
            expected_version=req.version,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise AppError(ErrorCode.SYS_409, 409, str(e))

    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return PostResponse(**post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> None:
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    deleted = await soft_delete_post(post_id, current_user["sub"], is_admin=is_admin)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found or not authorized."
        )

    # Audit log for admin delete (best-effort, via event bus)
    if is_admin:
        ip = request.client.host if request.client else None
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="ADMIN_DELETE_POST",
            target_type="post",
            target_id=str(post_id),
            ip_address=ip,
        )


@router.get("/{post_id}/history", response_model=PostHistoryResponse)
async def get_post_edit_history(
    post_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> PostHistoryResponse:
    # Verify post exists
    post = await get_post_by_id(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    history = await get_post_history(post_id)
    return PostHistoryResponse(history=history, total=len(history))  # type: ignore[arg-type]
