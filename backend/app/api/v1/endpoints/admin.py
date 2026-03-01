"""Admin dashboard and invite code management endpoints."""

from fastapi import APIRouter, Depends, Query

from app.core.deps import require_role
from app.services.dashboard import get_dashboard_stats
from app.services.invite_code import list_invite_codes

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
async def dashboard(
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> dict:
    stats = await get_dashboard_stats()
    return stats


@router.get("/invite-codes")
async def get_invite_codes(
    status_filter: str | None = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> dict:
    codes, total = await list_invite_codes(
        status_filter=status_filter, offset=offset, limit=limit
    )
    return {"codes": codes, "total": total}
