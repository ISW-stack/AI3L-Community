"""Social feature repository — friendships, follows, blocks (raw SQL)."""

import uuid

from app.core.database import get_pool


# ── Friendship ──────────────────────────────────────────────────────


async def insert_friendship(
    conn,
    friendship_id: uuid.UUID,
    requester_id: uuid.UUID,
    addressee_id: uuid.UUID,
    *,
    status: str = "PENDING",
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO friendships (id, requester_id, addressee_id, status)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        friendship_id,
        requester_id,
        addressee_id,
        status,
    )
    return dict(row)


async def find_friendship_by_id(conn, friendship_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow("SELECT * FROM friendships WHERE id = $1", friendship_id)
    return dict(row) if row else None


async def find_friendship_between(
    conn, user_a: uuid.UUID, user_b: uuid.UUID
) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT * FROM friendships
        WHERE (requester_id = $1 AND addressee_id = $2)
           OR (requester_id = $2 AND addressee_id = $1)
        """,
        user_a,
        user_b,
    )
    return dict(row) if row else None


async def accept_friendship(conn, friendship_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow(
        """
        UPDATE friendships
        SET status = 'ACCEPTED', updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        friendship_id,
    )
    return dict(row) if row else None


async def reject_friendship(conn, friendship_id: uuid.UUID) -> bool:
    result = await conn.execute("DELETE FROM friendships WHERE id = $1", friendship_id)
    return result == "DELETE 1"


async def delete_friendship_between(conn, user_a: uuid.UUID, user_b: uuid.UUID) -> bool:
    result = await conn.execute(
        """
        DELETE FROM friendships
        WHERE (requester_id = $1 AND addressee_id = $2)
           OR (requester_id = $2 AND addressee_id = $1)
        """,
        user_a,
        user_b,
    )
    return "DELETE" in result


async def find_friends(
    conn, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT
            f.id,
            f.created_at,
            u.id   AS friend_id,
            u.username,
            u.display_name,
            u.avatar_url,
            u.affiliation,
            COUNT(*) OVER() AS _total
        FROM friendships f
        JOIN users u ON u.id = CASE
            WHEN f.requester_id = $1 THEN f.addressee_id
            ELSE f.requester_id
        END
        WHERE f.status = 'ACCEPTED'
          AND (f.requester_id = $1 OR f.addressee_id = $1)
          AND u.is_deleted = false
        ORDER BY f.created_at DESC
        OFFSET $2 LIMIT $3
        """,
        user_id,
        offset,
        page_size,
    )
    if rows:
        total = rows[0]["_total"]
        return [
            {k: v for k, v in dict(r).items() if k != "_total"} for r in rows
        ], total
    return [], 0


async def find_pending_requests(
    conn, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT
            f.id,
            f.status,
            f.created_at,
            f.requester_id,
            req.username   AS requester_username,
            req.display_name AS requester_display_name,
            req.avatar_url AS requester_avatar_url,
            f.addressee_id,
            adr.username   AS addressee_username,
            adr.display_name AS addressee_display_name,
            adr.avatar_url AS addressee_avatar_url,
            COUNT(*) OVER() AS _total
        FROM friendships f
        JOIN users req ON req.id = f.requester_id
        JOIN users adr ON adr.id = f.addressee_id
        WHERE f.status = 'PENDING'
          AND (f.requester_id = $1 OR f.addressee_id = $1)
        ORDER BY f.created_at DESC
        OFFSET $2 LIMIT $3
        """,
        user_id,
        offset,
        page_size,
    )
    if rows:
        total = rows[0]["_total"]
        return [
            {k: v for k, v in dict(r).items() if k != "_total"} for r in rows
        ], total
    return [], 0


async def count_friends(conn, user_id: uuid.UUID) -> int:
    result = await conn.fetchval(
        """
        SELECT COUNT(*) FROM friendships
        WHERE status = 'ACCEPTED'
          AND (requester_id = $1 OR addressee_id = $1)
        """,
        user_id,
    )
    return int(result)


# ── Follow ──────────────────────────────────────────────────────────


async def insert_follow(
    conn, follow_id: uuid.UUID, follower_id: uuid.UUID, following_id: uuid.UUID
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO follows (id, follower_id, following_id)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        follow_id,
        follower_id,
        following_id,
    )
    return dict(row)


async def delete_follow(conn, follower_id: uuid.UUID, following_id: uuid.UUID) -> bool:
    result = await conn.execute(
        "DELETE FROM follows WHERE follower_id = $1 AND following_id = $2",
        follower_id,
        following_id,
    )
    return result == "DELETE 1"


async def delete_follows_between(conn, user_a: uuid.UUID, user_b: uuid.UUID) -> None:
    await conn.execute(
        """
        DELETE FROM follows
        WHERE (follower_id = $1 AND following_id = $2)
           OR (follower_id = $2 AND following_id = $1)
        """,
        user_a,
        user_b,
    )


async def find_followers(
    conn, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT
            f.id,
            f.created_at,
            u.id   AS user_id,
            u.username,
            u.display_name,
            u.avatar_url,
            COUNT(*) OVER() AS _total
        FROM follows f
        JOIN users u ON u.id = f.follower_id
        WHERE f.following_id = $1
          AND u.is_deleted = false
        ORDER BY f.created_at DESC
        OFFSET $2 LIMIT $3
        """,
        user_id,
        offset,
        page_size,
    )
    if rows:
        total = rows[0]["_total"]
        return [
            {k: v for k, v in dict(r).items() if k != "_total"} for r in rows
        ], total
    return [], 0


async def find_following(
    conn, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT
            f.id,
            f.created_at,
            u.id   AS user_id,
            u.username,
            u.display_name,
            u.avatar_url,
            COUNT(*) OVER() AS _total
        FROM follows f
        JOIN users u ON u.id = f.following_id
        WHERE f.follower_id = $1
          AND u.is_deleted = false
        ORDER BY f.created_at DESC
        OFFSET $2 LIMIT $3
        """,
        user_id,
        offset,
        page_size,
    )
    if rows:
        total = rows[0]["_total"]
        return [
            {k: v for k, v in dict(r).items() if k != "_total"} for r in rows
        ], total
    return [], 0


async def is_following(conn, follower_id: uuid.UUID, following_id: uuid.UUID) -> bool:
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM follows WHERE follower_id = $1 AND following_id = $2",
        follower_id,
        following_id,
    )
    return int(result) > 0


async def count_followers(conn, user_id: uuid.UUID) -> int:
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM follows WHERE following_id = $1",
        user_id,
    )
    return int(result)


async def count_following(conn, user_id: uuid.UUID) -> int:
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM follows WHERE follower_id = $1",
        user_id,
    )
    return int(result)


# ── Block ───────────────────────────────────────────────────────────


async def insert_block(
    conn, block_id: uuid.UUID, blocker_id: uuid.UUID, blocked_id: uuid.UUID
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO blocks (id, blocker_id, blocked_id)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        block_id,
        blocker_id,
        blocked_id,
    )
    return dict(row)


async def delete_block(conn, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> bool:
    result = await conn.execute(
        "DELETE FROM blocks WHERE blocker_id = $1 AND blocked_id = $2",
        blocker_id,
        blocked_id,
    )
    return result == "DELETE 1"


async def find_blocks(
    conn, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT
            b.id,
            b.created_at,
            b.blocked_id,
            u.username,
            u.display_name,
            u.avatar_url,
            COUNT(*) OVER() AS _total
        FROM blocks b
        JOIN users u ON u.id = b.blocked_id
        WHERE b.blocker_id = $1
          AND u.is_deleted = false
        ORDER BY b.created_at DESC
        OFFSET $2 LIMIT $3
        """,
        user_id,
        offset,
        page_size,
    )
    if rows:
        total = rows[0]["_total"]
        return [
            {k: v for k, v in dict(r).items() if k != "_total"} for r in rows
        ], total
    return [], 0


async def count_blocks(conn, user_id: uuid.UUID) -> int:
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM blocks WHERE blocker_id = $1",
        user_id,
    )
    return int(result)


async def is_blocked(conn, user_a: uuid.UUID, user_b: uuid.UUID) -> bool:
    """Check if EITHER user has blocked the other."""
    result = await conn.fetchval(
        """
        SELECT COUNT(*) FROM blocks
        WHERE (blocker_id = $1 AND blocked_id = $2)
           OR (blocker_id = $2 AND blocked_id = $1)
        """,
        user_a,
        user_b,
    )
    return int(result) > 0


async def find_all_blocks_raw(conn) -> list[dict]:
    rows = await conn.fetch("SELECT blocker_id, blocked_id FROM blocks")
    return [dict(r) for r in rows]


# ── Relationship status ─────────────────────────────────────────────


async def get_relationship_status(
    conn, user_id: uuid.UUID, target_id: uuid.UUID
) -> dict:
    """Return a dict with is_friend, is_following, is_followed_by, is_blocked,
    pending_request (null | 'sent' | 'received'), and friendship_id."""

    # Friendship
    friendship = await find_friendship_between(conn, user_id, target_id)
    is_friend = False
    pending_request = None
    friendship_id = None

    if friendship:
        friendship_id = str(friendship["id"])
        if friendship["status"] == "ACCEPTED":
            is_friend = True
        elif friendship["status"] == "PENDING":
            if friendship["requester_id"] == user_id:
                pending_request = "sent"
            else:
                pending_request = "received"

    # Follow
    following = await is_following(conn, user_id, target_id)
    followed_by = await is_following(conn, target_id, user_id)

    # Block
    blocked = await is_blocked(conn, user_id, target_id)

    return {
        "is_friend": is_friend,
        "is_following": following,
        "is_followed_by": followed_by,
        "is_blocked": blocked,
        "pending_request": pending_request,
        "friendship_id": friendship_id,
    }
