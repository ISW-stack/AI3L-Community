import sys

from loguru import logger


def setup_logging(level: str = "DEBUG", fmt: str = "json") -> None:
    logger.remove()

    if fmt == "json":
        logger.add(
            sys.stderr,
            level=level.upper(),
            format="{message}",
            serialize=True,
        )
    else:
        logger.add(
            sys.stderr,
            level=level.upper(),
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
        )

    logger.info("Logging configured", extra={"level": level, "format": fmt})
