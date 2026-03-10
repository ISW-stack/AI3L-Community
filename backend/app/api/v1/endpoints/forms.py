import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.constants import RATE_LIMIT_FORM_EXPORT, RATE_LIMIT_FORM_SUBMIT
from app.core.deps import get_current_user, require_role
from app.core.rate_limit import check_rate_limit
from app.repositories import sig_repo
from app.schemas.form import (
    FormCreateRequest,
    FormListResponse,
    FormResponseItem,
    FormResponseListResponse,
    FormResponseSchema,
    FormSubmitRequest,
    FormSubmitResponse,
    FormUpdateRequest,
)
from app.services.form import (
    create_form,
    get_form_by_id,
    list_form_responses,
    list_forms_by_sig,
    soft_delete_form,
    submit_response,
    update_form,
)

router = APIRouter(tags=["forms"])


async def _check_sig_admin(sig_id: uuid.UUID, user_id: str, role: str) -> bool:
    """Check if user is a platform admin or SIG ADMIN/SUB_ADMIN."""
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
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormResponseSchema:
    is_sig_admin = await _check_sig_admin(sig_id, current_user["sub"], current_user["role"])
    if not is_sig_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SIG admins can create forms.",
        )
    try:
        form = await create_form(
            sig_id=str(sig_id),
            user_id=current_user["sub"],
            title=req.title,
            description=req.description,
            banner_url=req.banner_url,
            deadline=req.deadline,
            max_respondents=req.max_respondents,
            questions=[q.model_dump() for q in req.questions],
            allow_non_members=req.allow_non_members,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    form["user_is_sig_admin"] = True
    return FormResponseSchema(**form)


@router.get("/sigs/{sig_id}/forms", response_model=FormListResponse)
async def get_sig_forms(
    sig_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> FormListResponse:
    forms, total = await list_forms_by_sig(sig_id, page=page, page_size=page_size)
    is_sig_admin = await _check_sig_admin(sig_id, current_user["sub"], current_user["role"])
    for f in forms:
        f["user_is_sig_admin"] = is_sig_admin
    return FormListResponse(
        forms=[FormResponseSchema(**f) for f in forms],
        total=total,
    )


@router.get("/forms/{form_id}", response_model=FormResponseSchema)
async def get_form(
    form_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> FormResponseSchema:
    form = await get_form_by_id(form_id)
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")
    is_sig_admin = await _check_sig_admin(
        uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
    )
    form["user_is_sig_admin"] = is_sig_admin
    return FormResponseSchema(**form)


@router.put("/forms/{form_id}", response_model=FormResponseSchema)
async def update_existing_form(
    form_id: uuid.UUID,
    req: FormUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormResponseSchema:
    # Fetch form to validate SIG ownership
    existing_form = await get_form_by_id(form_id)
    if existing_form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")

    is_sig_admin = await _check_sig_admin(
        uuid.UUID(existing_form["sig_id"]), current_user["sub"], current_user["role"]
    )
    if not is_sig_admin and existing_form["created_by"] != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SIG admins or the form creator can update this form.",
        )

    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN") or is_sig_admin
    try:
        form = await update_form(
            form_id=form_id,
            user_id=current_user["sub"],
            is_admin=is_admin,
            title=req.title,
            description=req.description,
            banner_url=req.banner_url,
            deadline=req.deadline,
            max_respondents=req.max_respondents,
            questions=[q.model_dump() for q in req.questions] if req.questions else None,
            allow_non_members=req.allow_non_members,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")
        is_admin = await _check_sig_admin(
            uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
        )

    try:
        deleted = await soft_delete_form(form_id, current_user["sub"], is_admin)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")


@router.get("/forms/{form_id}/responses", response_model=FormResponseListResponse)
async def get_form_responses(
    form_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormResponseListResponse:
    form = await get_form_by_id(form_id)
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")

    is_sig_admin = await _check_sig_admin(
        uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
    )
    if not is_sig_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SIG admins can view form responses.",
        )

    responses, total = await list_form_responses(form_id, page=page, page_size=page_size)
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
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FormSubmitResponse:
    user_id = current_user["sub"]
    if not await check_rate_limit(f"rl:form_submit:{user_id}:{form_id}", *RATE_LIMIT_FORM_SUBMIT):
        raise HTTPException(status_code=429, detail="Too many submissions. Try again later.")
    try:
        result = await submit_response(
            form_id=form_id,
            user_id=current_user["sub"],
            answers=req.answers,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        detail = str(e)
        if "already submitted" in detail.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except Exception as e:
        # Catch DB unique-violation (concurrent duplicate submit) gracefully
        err_str = str(e).lower()
        if "unique" in err_str or "duplicate" in err_str or "23505" in err_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted a response to this form.",
            )
        raise
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")

    is_sig_admin = await _check_sig_admin(
        uuid.UUID(form["sig_id"]), current_user["sub"], current_user["role"]
    )
    if not is_sig_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SIG admins can export form data.",
        )

    if not await check_rate_limit(f"rl:form_export:{user_id}:{form_id}", *RATE_LIMIT_FORM_EXPORT):
        raise HTTPException(status_code=429, detail="Export already in progress. Try again later.")

    from app.tasks.form_export import export_form_csv as export_task

    task = export_task.delay(str(form_id))
    return {"task_id": task.id}
