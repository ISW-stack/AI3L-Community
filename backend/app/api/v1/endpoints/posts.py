import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.constants import RATE_LIMIT_REACTION
from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode, RateLimitError
from app.core.event_bus import emit
from app.core.file_validation import sanitize_html
from app.core.rate_limit import check_rate_limit
from app.schemas.comment import ReactionRequest
from app.schemas.post import (
    BulkDeletePostsRequest,
    PinPostRequest,
    PostCreateRequest,
    PostHistoryResponse,
    PostListResponse,
    PostResponse,
    PostSearchRequest,
    PostUpdateRequest,
    SearchSuggestion,
    SearchSuggestionsResponse,
)
from app.services.post import (
    create_post,
    get_post_by_id,
    get_post_history,
    get_trending_posts,
    list_posts,
    pin_post,
    search_posts,
    soft_delete_post,
    toggle_post_reaction,
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
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return PostResponse(**post)


@router.get("", response_model=PostListResponse)
async def get_posts_list(
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    category_id: str | None = None,
    sig_id: str | None = None,
    author_id: str | None = None,
    sort: str = Query("newest", pattern="^(newest|oldest|most_comments|popular)$"),
    cursor: str | None = Query(None, description="Opaque cursor for keyset pagination"),
    current_user: dict = Depends(get_current_user),
) -> PostListResponse:
    try:
        result = await list_posts(
            page=page,
            page_size=page_size,
            category_id=category_id,
            sig_id=sig_id,
            author_id=author_id,
            sort=sort,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if cursor is not None:
        return PostListResponse(
            posts=result["posts"],  # type: ignore[arg-type]
            next_cursor=result["next_cursor"],
            has_more=result["has_more"],
        )
    return PostListResponse(
        posts=result["posts"],  # type: ignore[arg-type]
        total=result["total"],
        current_page=page,
        total_pages=result["total_pages"],
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
        sort=req.sort,
    )
    return PostListResponse(
        posts=posts,  # type: ignore[arg-type]
        total=total,
        current_page=req.page,
        total_pages=total_pages,
        has_more=req.page < total_pages,
    )


@router.get("/trending", response_model=list[PostResponse])
async def get_trending(
    current_user: dict = Depends(get_current_user),
) -> list[PostResponse]:
    posts = await get_trending_posts(limit=5, days=7)
    return [PostResponse(**p) for p in posts]  # type: ignore[arg-type]


@router.delete("/bulk", status_code=status.HTTP_200_OK)
async def bulk_delete_posts(
    req: BulkDeletePostsRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> dict:
    from app.services.audit import log_action
    from app.services.post import bulk_soft_delete

    count = await bulk_soft_delete(req.post_ids)
    await log_action(
        user_id=current_user["sub"],
        action="BULK_DELETE_POSTS",
        target_type="post",
        target_id=",".join(str(pid) for pid in req.post_ids),
    )
    return {"deleted_count": count}


@router.get("/suggestions", response_model=SearchSuggestionsResponse)
async def search_suggestions(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
) -> SearchSuggestionsResponse:
    """Return search suggestions for posts and keywords matching the query."""
    from app.repositories import post_repo

    posts = await post_repo.get_search_suggestions(q, limit=limit)
    keywords = await post_repo.get_keyword_suggestions(q, limit=limit)
    return SearchSuggestionsResponse(
        posts=[SearchSuggestion(id=str(p["id"]), title=p["title"]) for p in posts],
        keywords=keywords,
    )


@router.post("/{post_id}/reactions", response_model=PostResponse)
async def toggle_post_reaction_endpoint(
    post_id: uuid.UUID,
    req: ReactionRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> PostResponse:
    if not await check_rate_limit(
        f"rl:post_reaction:{current_user['sub']}", *RATE_LIMIT_REACTION
    ):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    result = await toggle_post_reaction(post_id, current_user["sub"], req.reaction)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return PostResponse(**result)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> PostResponse:
    post = await get_post_by_id(post_id, increment_view=True)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return PostResponse(**post)


@router.put("/{post_id}", response_model=PostResponse)
async def update_existing_post(
    post_id: uuid.UUID,
    req: PostUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> PostResponse:
    if not await check_rate_limit(f"edit_post:{current_user['sub']}", 30, 3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Edit rate limit exceeded. Please wait before editing again.",
        )
    if not any(
        [
            req.title,
            req.content,
            req.category_id is not None,
            req.keywords is not None,
            req.allow_comments is not None,
        ]
    ):
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
            caller_role=current_user["role"],
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

    # Audit log (best-effort, via event bus)
    ip = request.client.host if request.client else None
    if is_admin:
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="ADMIN_DELETE_POST",
            target_type="post",
            target_id=str(post_id),
            ip_address=ip,
        )
    else:
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="USER_DELETE_POST",
            target_type="post",
            target_id=str(post_id),
            ip_address=ip,
        )


@router.patch("/{post_id}/pin", response_model=dict)
async def toggle_pin(
    post_id: uuid.UUID,
    req: PinPostRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> dict:
    updated = await pin_post(post_id, req.is_pinned)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return {"is_pinned": req.is_pinned}


@router.get("/{post_id}/history", response_model=PostHistoryResponse)
async def get_post_edit_history(
    post_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> PostHistoryResponse:
    # Verify post exists
    post = await get_post_by_id(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    # Only post owner or admins can view edit history
    if str(post["author"]["id"]) != current_user["sub"] and current_user["role"] not in (
        "SUPER_ADMIN",
        "ADMIN",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view edit history.",
        )

    history = await get_post_history(post_id)
    return PostHistoryResponse(history=history, total=len(history))  # type: ignore[arg-type]
