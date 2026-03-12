import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.constants import RATE_LIMIT_CATEGORY_CRUD
from app.core.deps import get_current_user, require_role
from app.core.rate_limit import check_rate_limit
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.services.category import (
    category_exists,
    create_category,
    delete_category,
    get_category_by_id,
    list_categories,
    update_category,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
async def get_categories(
    response: Response,
    current_user: dict = Depends(get_current_user),
) -> CategoryListResponse:
    response.headers["Cache-Control"] = "private, max-age=60"
    categories = await list_categories()
    items = [
        CategoryResponse(
            id=str(c["id"]),
            name=c["name"],
            description=c.get("description"),
            post_count=c.get("post_count", 0),
        )
        for c in categories
    ]
    return CategoryListResponse(categories=items, total=len(items))


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> CategoryResponse:
    cat = await get_category_by_id(category_id)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    return CategoryResponse(
        id=str(cat["id"]),
        name=cat["name"],
        description=cat.get("description"),
        post_count=cat.get("post_count", 0),
    )


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_category(
    req: CategoryCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> CategoryResponse:
    if not await check_rate_limit(
        f"rl:category_crud:{current_user['sub']}", *RATE_LIMIT_CATEGORY_CRUD
    ):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    if await category_exists(req.name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists.")

    cat = await create_category(name=req.name, description=req.description)
    return CategoryResponse(
        id=str(cat["id"]),
        name=cat["name"],
        description=cat.get("description"),
    )


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_existing_category(
    category_id: uuid.UUID,
    req: CategoryUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> CategoryResponse:
    if not await check_rate_limit(
        f"rl:category_crud:{current_user['sub']}", *RATE_LIMIT_CATEGORY_CRUD
    ):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    cat = await update_category(category_id, name=req.name, description=req.description)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    return CategoryResponse(
        id=str(cat["id"]),
        name=cat["name"],
        description=cat.get("description"),
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_category(
    category_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> None:
    if not await check_rate_limit(
        f"rl:category_crud:{current_user['sub']}", *RATE_LIMIT_CATEGORY_CRUD
    ):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    deleted = await delete_category(category_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
