import uuid

from loguru import logger

from app.repositories import category_repo


async def create_category(name: str, description: str | None = None) -> dict:
    cat_id = uuid.uuid4()
    result = await category_repo.insert(cat_id, name, description)
    logger.info("Category created", extra={"category_id": str(cat_id), "name": name})
    return result


async def list_categories() -> list[dict]:
    return await category_repo.find_all_with_post_counts()


async def get_category_by_id(category_id: uuid.UUID) -> dict | None:
    return await category_repo.find_by_id_with_post_count(category_id)


async def update_category(
    category_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
) -> dict | None:
    current = await category_repo.find_by_id(category_id)
    if not current:
        return None

    new_name = name if name is not None else current["name"]
    new_desc = description if description is not None else current["description"]

    result = await category_repo.update(category_id, new_name, new_desc)
    if result:
        logger.info("Category updated", extra={"category_id": str(category_id)})
    return result


async def delete_category(category_id: uuid.UUID) -> bool:
    deleted = await category_repo.delete(category_id)
    if deleted:
        logger.info("Category deleted", extra={"category_id": str(category_id)})
    return deleted


async def category_exists(name: str) -> bool:
    return await category_repo.exists_by_name(name)
