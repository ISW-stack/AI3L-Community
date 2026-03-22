import uuid

from fastapi import APIRouter, Depends, Query

from app.core.constants import RATE_LIMIT_CITATION_SEARCH
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.schemas.citation import CitationEntryResponse, CitationListResponse, CitationSearchRequest
from app.services.citation import get_citations_of, get_citing, search_posts_for_citation

router = APIRouter(prefix="/citations", tags=["citations"])


@router.post("/posts/search-for-citation")
async def search_for_citation(
    req: CitationSearchRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> list[dict]:
    """Search posts for citation insertion."""
    if not await check_rate_limit(
        f"rl:citation_search:{current_user['sub']}", *RATE_LIMIT_CITATION_SEARCH
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    return await search_posts_for_citation(
        query=req.query,
        user_id=current_user["sub"],
        limit=req.limit,
    )


@router.get("/posts/{post_id}/cited-by", response_model=CitationListResponse)
async def get_cited_by(
    post_id: uuid.UUID,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CitationListResponse:
    """Get posts that cite this post ('Cited by' list)."""
    citations, total = await get_citations_of(post_id=post_id, page=page, page_size=page_size)
    return CitationListResponse(
        citations=[CitationEntryResponse(**c) for c in citations], total=total
    )


@router.get("/posts/{post_id}/citing", response_model=CitationListResponse)
async def get_citing_endpoint(
    post_id: uuid.UUID,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CitationListResponse:
    """Get posts this post cites ('References' list)."""
    citations, total = await get_citing(post_id=post_id, page=page, page_size=page_size)
    return CitationListResponse(
        citations=[CitationEntryResponse(**c) for c in citations], total=total
    )
