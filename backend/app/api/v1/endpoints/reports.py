import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import require_role
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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> PostReportListResponse:
    reports, total = await list_reports(status_filter=status_filter, offset=offset, limit=limit)
    return PostReportListResponse(
        reports=[PostReportResponse(**r) for r in reports],
        total=total,
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
