import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.constants import RATE_LIMIT_REPORT
from app.core.deps import require_role
from app.core.rate_limit import check_rate_limit
from app.schemas.report import (
    PostReportCreateRequest,
    PostReportListResponse,
    PostReportResponse,
    PostReportReviewRequest,
)
from app.services.post import get_post_by_id
from app.services.report import create_report, list_reports, review_report

router = APIRouter(tags=["reports"])


@router.post(
    "/posts/{post_id}/report",
    response_model=PostReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def report_post(
    post_id: uuid.UUID,
    req: PostReportCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> PostReportResponse:
    if not await check_rate_limit(f"rl:report:{current_user['sub']}", *RATE_LIMIT_REPORT):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    post = await get_post_by_id(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    try:
        report = await create_report(post_id, current_user["sub"], req.reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return PostReportResponse(**report)


@router.get("/admin/reports", response_model=PostReportListResponse)
async def get_reports(
    status_filter: str | None = None,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> PostReportListResponse:
    reports, total = await list_reports(status_filter=status_filter, page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PostReportListResponse(
        reports=[PostReportResponse(**r) for r in reports],
        total=total,
        current_page=page,
        total_pages=total_pages,
    )


@router.put("/admin/reports/{report_id}/review", response_model=PostReportResponse)
async def review_report_endpoint(
    report_id: uuid.UUID,
    req: PostReportReviewRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> PostReportResponse:
    report = await review_report(report_id, current_user["sub"], req.status)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found or already reviewed."
        )
    return PostReportResponse(**report)
