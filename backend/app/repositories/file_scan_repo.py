from app.core.database import get_pool


async def insert(file_key: str) -> dict:
    """Insert a new pending file scan record."""
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
        if row:
            return dict(row)
        # If ON CONFLICT hit, return existing record
        existing = await conn.fetchrow(
            "SELECT * FROM file_scans WHERE file_key = $1",
            file_key,
        )
        return dict(existing) if existing else {}


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
