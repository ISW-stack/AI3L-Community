import base64
import random
import string
import uuid
from io import BytesIO

from captcha.image import ImageCaptcha
from loguru import logger

from app.core.constants import CAPTCHA_LENGTH, CAPTCHA_TTL
from app.core.redis import get_redis


async def generate_captcha() -> tuple[str, str]:
    """Generate a captcha image. Returns (captcha_id, image_base64)."""
    redis = get_redis()
    captcha_id = str(uuid.uuid4())

    # Generate random code (uppercase + digits, no ambiguous chars)
    chars = string.ascii_uppercase.replace("O", "").replace("I", "") + string.digits.replace(
        "0", ""
    ).replace("1", "")
    code = "".join(random.choices(chars, k=CAPTCHA_LENGTH))

    # Generate image
    image_captcha = ImageCaptcha(width=160, height=60)
    image = image_captcha.generate_image(code)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    image_base64 = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

    # Store in Redis
    await redis.set(f"captcha:{captcha_id}", code.upper(), ex=CAPTCHA_TTL)
    logger.info("Captcha generated", extra={"captcha_id": captcha_id})

    return captcha_id, image_base64


async def verify_captcha(captcha_id: str, captcha_code: str) -> bool:
    """Verify and consume captcha. Returns True if valid."""
    redis = get_redis()
    key = f"captcha:{captcha_id}"
    # Atomic get-and-delete to prevent TOCTOU race
    stored_code = await redis.getdel(key)

    if stored_code is None:
        return False

    return bool(stored_code.upper() == captcha_code.upper())
