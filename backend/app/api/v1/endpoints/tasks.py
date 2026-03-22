from fastapi import APIRouter, Depends, Path

from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.schemas.form import TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
    task_id: str = Path(..., min_length=1, max_length=64),
) -> TaskStatusResponse:
    from celery.result import AsyncResult

    from app.celery_app import celery

    # Ownership check: MEMBER users can only access their own tasks
    if current_user["role"] not in ("SUPER_ADMIN", "ADMIN"):
        from app.core.redis import get_redis

        redis = get_redis()
        owner_id = await redis.get(f"task_owner:{task_id}")
        if owner_id is None:
            # TTL expired — fail closed
            raise AppError(ErrorCode.SYS_403, 403, "Task ownership could not be verified.")
        if owner_id != current_user["sub"]:
            raise AppError(ErrorCode.SYS_403, 403, "You do not have access to this task.")

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
