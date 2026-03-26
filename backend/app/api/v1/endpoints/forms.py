import uuid

import asyncpg
from fastapi import APIRouter, Depends, Query, Request, status

from app.core.constants import (
    DEFAULT_PAGE_SIZE_STANDALONE_FORMS,
    MAX_PAGE_SIZE,
    RATE_LIMIT_FORM_EXPORT,
    RATE_LIMIT_FORM_STATS,
    RATE_LIMIT_FORM_SUBMIT,
    RATE_LIMIT_STANDALONE_FORM,
)
from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.file_validation import sanitize_html
from app.core.rate_limit import check_rate_limit
from app.dependencies.sig_admin import require_sig_admin
from app.repositories import sig_repo
from app.schemas.form import (
    FormCreateRequest,
    FormListResponse,
    FormResponseItem,
    FormResponseListResponse,
    FormResponseSchema,
    FormStatsResponse,
    FormSubmitRequest,
    FormSubmitResponse,
    FormUpdateRequest,
    FormUserResponseSchema,
)
from app.services.form import (
    create_form,
    get_form_by_id,
    get_form_stats,
    get_user_response,
    list_form_responses,
    list_forms_by_sig,
)
from app.services.form import list_standalone_forms as list_standalone_forms_svc
from app.services.form import (
    soft_delete_form,
    submit_response,
    update_form,
)

router = APIRouter(tags=["forms"])


async def _is_sig_admin(sig_id: uuid.UUID, user_id: str, role: str) -> bool:
    """Return True if the user is a platform admin or holds ADMIN/SUB_ADMIN in the SIG."""
    if role in ("SUPER_ADMIN", "ADMIN"):
        return True
    member_role = await sig_repo.get_member_role(sig_id, uuid.UUID(user_id))
    return member_role in ("ADMIN", "SUB_ADMIN")


@router.post(
    "/sigs/{sig_id}/forms",
    response_model=FormResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_form(
    sig_id: uuid.UUID,
    req: FormCreateRequest,
    current_user: dict = Depends(require_sig_admin()),
) -> FormResponseSchema:
    try:
        form = await create_form(
            sig_id=str(sig_id),
            user_id=current_user["sub"],
            title=req.title,
            description=sanitize_html(req.description) if req.description else req.description,
            banner_url=req.banner_url,
            deadline=req.deadline,
            max_respondents=req.max_respondents,
            questions=[q.model_dump() for q in req.questions],
            allow_non_members=req.allow_non_members,
        )
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, str(e))
    form["user_is_sig_admin"] = True
    return FormResponseSchema(**form)


@router.get("/sigs/{sig_id}/forms", response_model=FormListResponse)
async def get_sig_forms(
    sig_id: uuid.UUID,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> FormListResponse:
    forms, total = await list_forms_by_sig(sig_id, page=page, page_size=page_size)
    is_admin = await _is_sig_admin(sig_id, current_user["sub"], current_user["role"])
    for f in forms:
        f["user_is_sig_admin"] = is_admin
    return FormListResponse(
        forms=[FormResponseSchema(**f) for f in forms],
        total=total,
    )


@router.post(
    "/forms",
    response_model=FormResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_standalone_form(
    req: FormCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormResponseSchema:
    """Create a standalone form (not attached to any SIG)."""
    user_id = current_user["sub"]
    if not await check_rate_limit(f"rl:standalone_form:{user_id}", *RATE_LIMIT_STANDALONE_FORM):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    try:
        form = await create_form(
            sig_id=None,
            user_id=user_id,
            title=req.title,
            description=sanitize_html(req.description) if req.description else req.description,
            banner_url=req.banner_url,
            deadline=req.deadline,
            max_respondents=req.max_respondents,
            questions=[q.model_dump() for q in req.questions],
            allow_non_members=True,
        )
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, str(e))
    return FormResponseSchema(**form)


@router.get("/forms", response_model=FormListResponse)
async def list_standalone_forms_endpoint(
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(DEFAULT_PAGE_SIZE_STANDALONE_FORMS, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(None, max_length=200),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormListResponse:
    """List standalone forms owned by the current user."""
    forms, total = await list_standalone_forms_svc(
        user_id=uuid.UUID(current_user["sub"]), page=page, page_size=page_size, q=q
    )
    return FormListResponse(
        forms=[FormResponseSchema(**f) for f in forms],
        total=total,
    )


@router.get("/forms/{form_id}/my-response", response_model=FormUserResponseSchema | None)
async def get_my_response(
    form_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> FormUserResponseSchema | None:
    form = await get_form_by_id(form_id)
    if form is None:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")
    # If form restricts access to SIG members only, verify membership
    # Standalone forms (sig_id is None) skip this check
    if form.get("sig_id") and not form.get("allow_non_members", False):
        is_admin = await _is_sig_admin(
            uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
        )
        if not is_admin:
            member_role = await sig_repo.get_member_role(
                uuid.UUID(form["sig_id"]), uuid.UUID(current_user["sub"])
            )
            if member_role is None:
                raise AppError(
                    ErrorCode.SYS_403,
                    status.HTTP_403_FORBIDDEN,
                    "Only SIG members can view this form.",
                )
    response = await get_user_response(form_id, current_user["sub"])
    if response is None:
        return None
    return FormUserResponseSchema(**response)


@router.get("/forms/{form_id}/stats", response_model=FormStatsResponse)
async def get_form_statistics(
    form_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormStatsResponse:
    user_id = current_user["sub"]
    if not await check_rate_limit(f"rl:form_stats:{user_id}:{form_id}", *RATE_LIMIT_FORM_STATS):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    form = await get_form_by_id(form_id)
    if form is None:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")
    is_creator = form["created_by"] == current_user["sub"]
    if form.get("sig_id"):
        is_admin = await _is_sig_admin(
            uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
        )
    else:
        # Standalone form — only platform admins or the creator
        is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    if not is_admin and not is_creator:
        raise AppError(
            ErrorCode.SYS_403,
            status.HTTP_403_FORBIDDEN,
            "Only the form creator or admins can view form statistics.",
        )
    try:
        stats = await get_form_stats(form_id)
    except ValueError as e:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, str(e))
    return FormStatsResponse(**stats)


@router.get("/forms/{form_id}", response_model=FormResponseSchema)
async def get_form(
    form_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> FormResponseSchema:
    user_id = current_user["sub"]
    form = await get_form_by_id(form_id, user_id=user_id)
    if form is None:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")
    if form.get("sig_id"):
        is_admin = await _is_sig_admin(
            uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
        )
        # If form restricts access to SIG members only, verify membership
        if not form.get("allow_non_members", False) and not is_admin:
            member_role = await sig_repo.get_member_role(
                uuid.UUID(form["sig_id"]), uuid.UUID(current_user["sub"])
            )
            if member_role is None:
                raise AppError(
                    ErrorCode.SYS_403,
                    status.HTTP_403_FORBIDDEN,
                    "Only SIG members can view this form.",
                )
    else:
        # F-14: Standalone form creator should see admin controls too
        is_admin = (
            current_user["role"] in ("SUPER_ADMIN", "ADMIN")
            or form["created_by"] == current_user["sub"]
        )
    form["user_is_sig_admin"] = is_admin
    return FormResponseSchema(**form)


@router.put("/forms/{form_id}", response_model=FormResponseSchema)
async def update_existing_form(
    form_id: uuid.UUID,
    req: FormUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormResponseSchema:
    # Fetch form to validate ownership
    existing_form = await get_form_by_id(form_id)
    if existing_form is None:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")

    if existing_form.get("sig_id"):
        is_admin = await _is_sig_admin(
            uuid.UUID(existing_form["sig_id"]), current_user["sub"], current_user["role"]
        )
    else:
        # Standalone form — only platform admins or the creator
        is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    if not is_admin and existing_form["created_by"] != current_user["sub"]:
        raise AppError(
            ErrorCode.SYS_403,
            status.HTTP_403_FORBIDDEN,
            "Only admins or the form creator can update this form.",
        )

    # Note: _is_sig_admin() already checks platform admin roles, no need to re-check
    try:
        form = await update_form(
            form_id=form_id,
            user_id=current_user["sub"],
            is_admin=is_admin,
            title=req.title,
            description=sanitize_html(req.description) if req.description else req.description,
            banner_url=req.banner_url,
            deadline=req.deadline,
            max_respondents=req.max_respondents,
            questions=[q.model_dump() for q in req.questions] if req.questions else None,
            allow_non_members=req.allow_non_members,
            provided_fields=req.model_fields_set,
        )
    except PermissionError as e:
        raise AppError(ErrorCode.SYS_403, status.HTTP_403_FORBIDDEN, str(e))
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, str(e))
    if form is None:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")
    form["user_is_sig_admin"] = True
    return FormResponseSchema(**form)


@router.delete("/forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form(
    form_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> None:
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")

    # If not a platform admin, check if user is a SIG admin for the form's SIG
    if not is_admin:
        form = await get_form_by_id(form_id)
        if form is None:
            raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")
        if form.get("sig_id"):
            is_admin = await _is_sig_admin(
                uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
            )

    try:
        deleted = await soft_delete_form(form_id, current_user["sub"], is_admin)
    except PermissionError as e:
        raise AppError(ErrorCode.SYS_403, status.HTTP_403_FORBIDDEN, str(e))
    if not deleted:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")


@router.get("/forms/{form_id}/responses", response_model=FormResponseListResponse)
async def get_form_responses(
    form_id: uuid.UUID,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormResponseListResponse:
    form = await get_form_by_id(form_id)
    if form is None:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")

    if form.get("sig_id"):
        is_admin = await _is_sig_admin(
            uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
        )
    else:
        # Standalone form — only platform admins or the creator can view responses
        is_admin = (
            current_user["role"] in ("SUPER_ADMIN", "ADMIN")
            or form["created_by"] == current_user["sub"]
        )
    if not is_admin:
        # F-58: Both "form not found" and "not authorized" return 404 to prevent
        # timing oracle that could reveal form existence to unauthorized users.
        raise AppError(
            ErrorCode.SYS_404,
            status.HTTP_404_NOT_FOUND,
            "Form not found.",
        )

    responses, total = await list_form_responses(
        form_id, page=page, page_size=page_size, viewer_id=current_user["sub"]
    )
    return FormResponseListResponse(
        responses=[FormResponseItem(**r) for r in responses], total=total
    )


@router.post(
    "/forms/{form_id}/submit",
    response_model=FormSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_form_response(
    form_id: uuid.UUID,
    req: FormSubmitRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> FormSubmitResponse:
    user_id = current_user["sub"]
    if not await check_rate_limit(f"rl:form_submit:{user_id}:{form_id}", *RATE_LIMIT_FORM_SUBMIT):
        raise AppError(ErrorCode.SYS_429, 429, "Too many submissions. Try again later.")
    # Additional IP-based rate limit for guests (each guest session gets unique ID)
    if current_user.get("role") == "GUEST":
        from app.core.rate_limit import get_client_ip

        client_ip = get_client_ip(request) or "unknown"
        if not await check_rate_limit(f"rl:form_submit_ip:{client_ip}:{form_id}", 5, 3600):
            raise AppError(ErrorCode.SYS_429, 429, "Too many submissions from this IP.")
    is_guest = current_user.get("role") == "GUEST"
    try:
        result = await submit_response(
            form_id=form_id,
            user_id=current_user["sub"],
            answers=req.answers,
            is_guest=is_guest,
        )
    except PermissionError as e:
        raise AppError(ErrorCode.SYS_403, status.HTTP_403_FORBIDDEN, str(e))
    except ValueError as e:
        detail = str(e)
        if "already submitted" in detail.lower():
            raise AppError(ErrorCode.SYS_409, status.HTTP_409_CONFLICT, detail)
        raise AppError(ErrorCode.SYS_422, 422, detail)
    except asyncpg.UniqueViolationError:
        raise AppError(
            ErrorCode.SYS_409,
            status.HTTP_409_CONFLICT,
            "You have already submitted a response to this form.",
        )
    return FormSubmitResponse(**result)


@router.post(
    "/forms/{form_id}/export",
    status_code=status.HTTP_202_ACCEPTED,
)
async def export_form_csv(
    form_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    user_id = current_user["sub"]
    form = await get_form_by_id(form_id)
    if form is None:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Form not found.")

    if form.get("sig_id"):
        is_admin = await _is_sig_admin(
            uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
        )
    else:
        # Standalone form — only platform admins or the creator can export
        is_admin = (
            current_user["role"] in ("SUPER_ADMIN", "ADMIN")
            or form["created_by"] == current_user["sub"]
        )
    if not is_admin:
        raise AppError(
            ErrorCode.SYS_403,
            status.HTTP_403_FORBIDDEN,
            "Only admins or the form creator can export form data.",
        )

    if not await check_rate_limit(f"rl:form_export:{user_id}:{form_id}", *RATE_LIMIT_FORM_EXPORT):
        raise AppError(ErrorCode.SYS_429, 429, "Export already in progress. Try again later.")

    from app.tasks.form_export import export_form_csv as export_task

    task = export_task.delay(str(form_id))

    # Store task ownership in Redis so the status endpoint can verify access
    from app.core.redis import get_redis

    redis = get_redis()
    await redis.set(f"task_owner:{task.id}", user_id, ex=86400)

    return {"task_id": task.id}
