from loguru import logger

from app.repositories import site_settings_repo

ABOUT_INTRO_PHOTO = "about_intro_photo"
ABOUT_INTRO_BIO = "about_intro_bio"
ABOUT_CHAIR_PHOTO = "about_chair_photo"
ABOUT_CHAIR_BIO = "about_chair_bio"

_ABOUT_KEYS = [ABOUT_INTRO_PHOTO, ABOUT_INTRO_BIO, ABOUT_CHAIR_PHOTO, ABOUT_CHAIR_BIO]


async def get_about_intro() -> dict[str, str]:
    """Return Chair and Co-Chair photo keys and bio text."""
    data = await site_settings_repo.get_many(_ABOUT_KEYS)
    return {
        "photo_key": data.get(ABOUT_INTRO_PHOTO, ""),
        "bio": data.get(ABOUT_INTRO_BIO, ""),
        "chair_photo_key": data.get(ABOUT_CHAIR_PHOTO, ""),
        "chair_bio": data.get(ABOUT_CHAIR_BIO, ""),
    }


async def update_about_intro_photo(photo_key: str) -> None:
    await site_settings_repo.upsert(ABOUT_INTRO_PHOTO, photo_key)
    logger.info("About co-chair photo updated", extra={"photo_key": photo_key})


async def update_about_intro_bio(bio: str) -> None:
    await site_settings_repo.upsert(ABOUT_INTRO_BIO, bio)
    logger.info("About co-chair bio updated")


async def update_chair_photo(photo_key: str) -> None:
    await site_settings_repo.upsert(ABOUT_CHAIR_PHOTO, photo_key)
    logger.info("About chair photo updated", extra={"photo_key": photo_key})


async def update_chair_bio(bio: str) -> None:
    await site_settings_repo.upsert(ABOUT_CHAIR_BIO, bio)
    logger.info("About chair bio updated")
