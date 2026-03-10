from fastapi import APIRouter, Depends

from app.core.deps import require_role
from app.schemas.form import TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> TaskStatusResponse:
    from celery.result import AsyncResult

    from app.celery_app import celery

    result = AsyncResult(task_id, app=celery)

    download_url = None
    task_result = None
    if result.state == "SUCCESS" and result.result:
        download_url = result.result.get("download_url")
        task_result = result.result if isinstance(result.result, dict) else None

    return TaskStatusResponse(
        task_id=task_id,
        status=result.state,
        download_url=download_url,
        result=task_result,
    )
