import asyncpg
from loguru import logger

_pool: asyncpg.Pool | None = None


async def init_db_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    # Convert SQLAlchemy-style DSN to asyncpg-style
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=10,
        max_size=30,
        command_timeout=60,
    )
    logger.info("Database connection pool initialized", extra={"min_size": 10, "max_size": 30})
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


async def get_pool_stats() -> dict[str, int] | None:
    """Return pool utilization info if the pool is initialized.

    Returns a dict with ``size``, ``free``, and ``in_use`` keys,
    or ``None`` if the pool has not been created yet.
    """
    if _pool is None:
        return None
    size = _pool.get_size()
    free = _pool.get_idle_size()
    return {
        "size": size,
        "free": free,
        "in_use": size - free,
    }
