import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.constants import RATE_LIMIT_REACTION, RATE_LIMIT_SEARCH_SUGGESTIONS
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode, RateLimitError
from app.core.event_bus import emit
from app.core.file_validation import sanitize_html
from app.core.rate_limit import check_rate_limit, get_client_ip
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
    content = sanitize_html(req.content)
    from app.core.file_validation import post_process_citations

    content = post_process_citations(content)
    if not content or not content.strip():
        raise AppError(ErrorCode.SYS_422, 422, "Content cannot be empty after sanitization.")
    try:
        post = await create_post(
            user_id=current_user["sub"],
            title=req.title,
            content=content,
            category_id=req.category_id,
            sig_id=req.sig_id,
            keywords=req.keywords,
            allow_comments=req.allow_comments,
            post_type=req.type,
        )
    except RateLimitError as e:
        raise AppError(ErrorCode.SYS_429, 429, str(e))
    except PermissionError as e:
        raise AppError(ErrorCode.SYS_403, 403, str(e))
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, str(e))

    return PostResponse(**post)


@router.get("", response_model=PostListResponse)
async def get_posts_list(
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    category_id: str | None = None,
    sig_id: str | None = None,
    author_id: str | None = None,
    sort: str = Query(
        "newest", pattern="^(newest|oldest|most_comments|popular|most_answers|unanswered)$"
    ),
    cursor: str | None = Query(None, description="Opaque cursor for keyset pagination"),
    type: str | None = Query(None, pattern="^(post|question)$"),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")),
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
            post_type=type,
            viewer_id=current_user["sub"],
        )
    except ValueError:
        raise AppError(ErrorCode.SYS_422, 422, "Invalid cursor.")

    if cursor is not None:
        return PostListResponse(
            posts=cast(list[Any], result["posts"]),
            next_cursor=result["next_cursor"],
            has_more=result["has_more"],
        )
    return PostListResponse(
        posts=cast(list[Any], result["posts"]),
        total=result["total"],
        page=page,
        total_pages=result["total_pages"],
        next_cursor=result.get("next_cursor"),
        has_more=result.get("has_more"),
    )


@router.post("/search", response_model=PostListResponse)
async def search_posts_endpoint(
    req: PostSearchRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")),
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
        post_type=req.type,
        viewer_id=current_user["sub"],
    )
    return PostListResponse(
        posts=cast(list[Any], posts),
        total=total,
        page=req.page,
        total_pages=total_pages,
        has_more=req.page < total_pages,
    )


@router.get("/trending", response_model=list[PostResponse])
async def get_trending(
    type: str | None = Query(None, pattern="^(post|question)$"),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")),
) -> list[PostResponse]:
    posts = await get_trending_posts(limit=5, days=7, viewer_id=current_user["sub"], post_type=type)
    return [PostResponse(**cast(dict[str, Any], p)) for p in posts]


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
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")),
) -> SearchSuggestionsResponse:
    """Return search suggestions for posts and keywords matching the query."""
    if not await check_rate_limit(
        f"rl:suggestions:{current_user['sub']}", *RATE_LIMIT_SEARCH_SUGGESTIONS
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    from app.repositories import post_repo

    viewer_id = current_user["sub"]
    posts = await post_repo.get_search_suggestions(q, limit=limit, viewer_id=viewer_id)
    keywords = await post_repo.get_keyword_suggestions(q, limit=limit, viewer_id=viewer_id)
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
    if not await check_rate_limit(f"rl:post_reaction:{current_user['sub']}", *RATE_LIMIT_REACTION):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    # M-10: Check if reactor is blocked by post author or vice versa
    from app.core.blacklist import get_blocked_user_ids
    from app.core.redis import get_redis
    from app.repositories import post_repo

    post_owner_id = await post_repo.find_owner_id(post_id)
    if post_owner_id and post_owner_id != current_user["sub"]:
        redis = get_redis()
        blocked_ids = await get_blocked_user_ids(redis, current_user["sub"])
        if post_owner_id in blocked_ids:
            raise AppError(ErrorCode.SYS_403, 403, "Cannot react to this post.")
        owner_blocked = await get_blocked_user_ids(redis, post_owner_id)
        if current_user["sub"] in owner_blocked:
            raise AppError(ErrorCode.SYS_403, 403, "Cannot react to this post.")

    result = await toggle_post_reaction(post_id, current_user["sub"], req.reaction)
    if result is None:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found.")
    return PostResponse(**result)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")),
) -> PostResponse:
    post = await get_post_by_id(post_id, increment_view=True, viewer_id=current_user["sub"])
    if post is None:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found.")
    return PostResponse(**post)


@router.put("/{post_id}", response_model=PostResponse)
async def update_existing_post(
    post_id: uuid.UUID,
    req: PostUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> PostResponse:
    if not await check_rate_limit(f"edit_post:{current_user['sub']}", 30, 3600):
        raise AppError(
            ErrorCode.SYS_429, 429, "Edit rate limit exceeded. Please wait before editing again."
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
        raise AppError(ErrorCode.SYS_422, 422, "At least one field must be provided.")

    if req.title is not None and not req.title.strip():
        raise AppError(ErrorCode.SYS_422, 422, "Title cannot be empty.")

    content = sanitize_html(req.content) if req.content else None
    if content is not None and not content.strip():
        raise AppError(ErrorCode.SYS_422, 422, "Content cannot be empty after sanitization.")
    if content:
        from app.core.file_validation import post_process_citations

        content = post_process_citations(content)
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
        raise AppError(ErrorCode.SYS_403, 403, str(e))
    except ValueError as e:
        raise AppError(ErrorCode.SYS_409, 409, str(e))

    if post is None:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found.")
    return PostResponse(**post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> None:
    is_admin = current_user["role"] == "SUPER_ADMIN"
    deleted = await soft_delete_post(post_id, current_user["sub"], is_admin=is_admin)
    if not deleted:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found or not authorized.")

    # Audit log (best-effort, via event bus)
    ip = get_client_ip(request)
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
    post = await get_post_by_id(post_id)
    if post is None:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found.")

    # For SIG posts, only SIG admins or SUPER_ADMIN may pin/unpin
    if post.get("sig_id") and current_user["role"] != "SUPER_ADMIN":
        from app.repositories import sig_repo

        sig_role = await sig_repo.get_member_role(
            uuid.UUID(post["sig_id"]), uuid.UUID(current_user["sub"])
        )
        if sig_role != "ADMIN":
            raise AppError(ErrorCode.SYS_403, 403, "Only SIG admins can pin posts in this SIG.")

    updated = await pin_post(post_id, req.is_pinned)
    if not updated:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found.")
    return {"is_pinned": req.is_pinned}


@router.get("/{post_id}/history", response_model=PostHistoryResponse)
async def get_post_edit_history(
    post_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")),
) -> PostHistoryResponse:
    # Verify post exists
    post = await get_post_by_id(post_id)
    if post is None:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found.")
    # Only post owner or admins can view edit history
    if str(post["author"]["id"]) != current_user["sub"] and current_user["role"] not in (
        "SUPER_ADMIN",
        "ADMIN",
    ):
        raise AppError(ErrorCode.SYS_403, 403, "Not authorized to view edit history.")

    history, total = await get_post_history(post_id)
    return PostHistoryResponse(history=cast(list[Any], history), total=total)
