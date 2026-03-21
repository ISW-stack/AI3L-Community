from loguru import logger

from app.repositories import site_settings_repo

ABOUT_INTRO_PHOTO = "about_intro_photo"
ABOUT_INTRO_BIO = "about_intro_bio"

_ABOUT_KEYS = [ABOUT_INTRO_PHOTO, ABOUT_INTRO_BIO]


async def get_about_intro() -> dict[str, str]:
    """Return the about introduction photo key and bio text."""
    data = await site_settings_repo.get_many(_ABOUT_KEYS)
    return {
        "photo_key": data.get(ABOUT_INTRO_PHOTO, ""),
        "bio": data.get(ABOUT_INTRO_BIO, ""),
    }


async def update_about_intro_photo(photo_key: str) -> None:
    await site_settings_repo.upsert(ABOUT_INTRO_PHOTO, photo_key)
    logger.info("About intro photo updated", extra={"photo_key": photo_key})


async def update_about_intro_bio(bio: str) -> None:
    await site_settings_repo.upsert(ABOUT_INTRO_BIO, bio)
    logger.info("About intro bio updated")
