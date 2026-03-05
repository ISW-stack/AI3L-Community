import uuid

from loguru import logger

from app.repositories import contributor_repo


async def list_contributors() -> list[dict]:
    return await contributor_repo.find_all()


async def get_contributor(contributor_id: uuid.UUID) -> dict | None:
    return await contributor_repo.find_by_id(contributor_id)


async def create_contributor(
    github_username: str,
    display_name: str,
    role: str,
    display_order: int = 0,
) -> dict:
    contributor_id = uuid.uuid4()
    result = await contributor_repo.insert(
        contributor_id, github_username, display_name, role, display_order
    )
    logger.info(
        "Contributor created",
        extra={"contributor_id": str(contributor_id), "github": github_username},
    )
    return result


async def update_contributor(
    contributor_id: uuid.UUID,
    github_username: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
    display_order: int | None = None,
) -> dict | None:
    current = await contributor_repo.find_by_id(contributor_id)
    if not current:
        return None

    new_github = github_username if github_username is not None else current["github_username"]
    new_name = display_name if display_name is not None else current["display_name"]
    new_role = role if role is not None else current["role"]
    new_order = display_order if display_order is not None else current["display_order"]

    result = await contributor_repo.update(
        contributor_id, new_github, new_name, new_role, new_order
    )
    if result:
        logger.info("Contributor updated", extra={"contributor_id": str(contributor_id)})
    return result


async def delete_contributor(contributor_id: uuid.UUID) -> bool:
    deleted = await contributor_repo.delete(contributor_id)
    if deleted:
        logger.info("Contributor deleted", extra={"contributor_id": str(contributor_id)})
    return deleted


async def github_username_exists(github_username: str) -> bool:
    return await contributor_repo.exists_by_github(github_username)
