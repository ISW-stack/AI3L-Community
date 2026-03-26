from app.core.database import get_pool


async def insert(file_key: str) -> dict | None:
    """Insert a new pending file scan record (skip if already exists)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO file_scans (file_key)
            VALUES ($1)
            ON CONFLICT (file_key) DO NOTHING
            RETURNING *
            """,
            file_key,
        )
        if row is None:
            row = await conn.fetchrow("SELECT * FROM file_scans WHERE file_key = $1", file_key)
        return dict(row) if row else None


async def find_by_key(file_key: str) -> dict | None:
    """Find a file scan record by file_key."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM file_scans WHERE file_key = $1",
            file_key,
        )
        return dict(row) if row else None


async def update_status(
    file_key: str,
    status: str,
    scan_id: str | None = None,
    positives: int | None = None,
    total: int | None = None,
) -> None:
    """Update the scan result for a file."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE file_scans
            SET status = $1, scan_id = $2, positives = $3, total = $4, updated_at = NOW()
            WHERE file_key = $5
            """,
            status,
            scan_id,
            positives,
            total,
            file_key,
        )


async def delete_by_key(file_key: str) -> None:
    """Delete a file scan record by file_key."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM file_scans WHERE file_key = $1",
            file_key,
        )


async def is_clean(file_key: str) -> bool:
    """Return True if the file has been scanned and is clean.

    Returns True if no scan record exists (legacy files uploaded before scanning
    was introduced, or file types that are not scanned).
    Returns False if the scan record exists with a non-clean status (pending/malicious/unknown).
    """
    record = await find_by_key(file_key)
    if record is None:
        return True  # No scan record → pre-scanning legacy file, allow
    return record.get("status") == "clean"


async def delete_old_completed(days: int = 30) -> int:
    """Delete completed scan records older than *days*. Returns count deleted."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM file_scans "
            "WHERE status IN ('clean', 'malicious') "
            "AND updated_at < NOW() - make_interval(days => $1)",
            days,
        )
        # asyncpg returns "DELETE <n>"
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0
