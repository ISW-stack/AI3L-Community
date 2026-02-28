from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_role
from app.schemas.category import CategoryCreateRequest, CategoryListResponse, CategoryResponse
from app.services.category import category_exists, create_category, list_categories

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
async def get_categories() -> CategoryListResponse:
    categories = await list_categories()
    items = [
        CategoryResponse(
            id=str(c["id"]),
            name=c["name"],
            description=c.get("description"),
        )
        for c in categories
    ]
    return CategoryListResponse(categories=items, total=len(items))


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_category(
    req: CategoryCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> CategoryResponse:
    if await category_exists(req.name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists.")

    cat = await create_category(name=req.name, description=req.description)
    return CategoryResponse(
        id=str(cat["id"]),
        name=cat["name"],
        description=cat.get("description"),
    )
