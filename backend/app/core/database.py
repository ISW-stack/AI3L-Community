import asyncpg
from loguru import logger

_pool: asyncpg.Pool | None = None


async def init_db_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    # Convert SQLAlchemy-style DSN to asyncpg-style
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=5,
        max_size=15,
        command_timeout=30,
    )
    logger.info("Database connection pool initialized", extra={"min_size": 5, "max_size": 15})
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db_pool() first.")
    return _pool
