"""Daily friend recommendation computation task."""

import json
import uuid
from typing import Any

from loguru import logger

from app.celery_app import celery
from app.core.constants import (
    RECOMMENDATION_BATCH_SIZE,
    RECOMMENDATION_DISMISSED_RETENTION_DAYS,
    RECOMMENDATION_MAX_PER_USER,
    RECOMMENDATION_MAX_USERS,
    RECOMMENDATION_MIN_SCORE,
    RECOMMENDATION_MIN_USERS,
)
from app.tasks.async_runner import run_async as _run_async
from app.tasks.utils import ensure_pool as _ensure_pool


async def _compute_recommendations_async() -> dict[str, int]:
    """Async implementation of recommendation computation."""
    await _ensure_pool()

    from app.core.database import get_pool

    pool = get_pool()

    # Hold the lock connection open for the entire duration so the
    # session-level advisory lock is released on the SAME connection.
    async with pool.acquire() as lock_conn:
        lock_acquired = await lock_conn.fetchval(
            "SELECT pg_try_advisory_lock(hashtext('compute_recommendations'))"
        )
        if not lock_acquired:
            logger.info(
                "Skipping recommendation recompute — another task holds the lock"
            )
            return {"total": 0, "users": 0, "skipped": True, "reason": "lock_held"}

        try:
            return await _compute_recommendations_inner(pool)
        finally:
            await lock_conn.execute(
                "SELECT pg_advisory_unlock(hashtext('compute_recommendations'))"
            )


async def _compute_recommendations_inner(pool: Any) -> dict[str, int]:
    """Core computation — lock is held by caller."""

    # Phase 1: Check minimum user count (read-only, short)
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM users "
            "WHERE is_deleted = false AND is_banned = false AND role != 'GUEST'"
        )
    if count < RECOMMENDATION_MIN_USERS:
        logger.info("Not enough users (%d) for recommendations", count)
        return {"total": 0, "users": 0, "skipped": True}

    if count > RECOMMENDATION_MAX_USERS:
        logger.warning(
            "Too many users (%d > %d) for CROSS JOIN recommendations, "
            "processing in batches",
            count,
            RECOMMENDATION_MAX_USERS,
        )

    # Phase 2: Compute recommendations per batch (read-only queries)
    all_recs: list[dict[str, Any]] = []
    users_with_recs = 0
    last_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

    while True:
        async with pool.acquire() as conn:
            batch = [
                row["id"]
                for row in await conn.fetch(
                    "SELECT id FROM users "
                    "WHERE is_deleted = false AND is_banned = false "
                    "AND role != 'GUEST' AND id > $1 "
                    "ORDER BY id LIMIT $2",
                    last_id,
                    RECOMMENDATION_BATCH_SIZE,
                )
            ]
        if not batch:
            break
        last_id = batch[-1]

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                _RECOMMENDATION_BATCH_SQL,
                batch,
                RECOMMENDATION_MAX_PER_USER,
            )

        # Group by user, take top N
        user_recs: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for row in rows:
            uid = row["user_id"]
            if uid not in user_recs:
                user_recs[uid] = []
            if len(user_recs[uid]) < RECOMMENDATION_MAX_PER_USER:
                score = float(row["total_score"])
                if score >= RECOMMENDATION_MIN_SCORE:
                    reasons = _build_reasons(row)
                    user_recs[uid].append(
                        {
                            "id": uuid.uuid4(),
                            "user_id": uid,
                            "recommended_user_id": row["candidate_id"],
                            "score": score,
                            "reasons": json.dumps(reasons),
                        }
                    )

        batch_total = sum(len(r) for r in user_recs.values())
        users_with_recs += len(user_recs)
        for recs in user_recs.values():
            all_recs.extend(recs)

    # Phase 3: Atomic swap — DELETE old + INSERT all new in one short transaction
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM friend_recommendations")
            if all_recs:
                await conn.executemany(
                    """
                    INSERT INTO friend_recommendations
                        (id, user_id, recommended_user_id, score, reasons)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    """,
                    [
                        (
                            r["id"],
                            r["user_id"],
                            r["recommended_user_id"],
                            r["score"],
                            r["reasons"],
                        )
                        for r in all_recs
                    ],
                )

    total = len(all_recs)
    logger.info("Computed %d recommendations for %d users", total, users_with_recs)
    return {"total": total, "users": users_with_recs, "skipped": False}


def _build_reasons(row: Any) -> list[dict[str, Any]]:
    """Build structured reasons list from score components."""
    reasons: list[dict[str, Any]] = []
    if row.get("common_sigs", 0) > 0:
        reasons.append({"type": "common_sig", "count": int(row["common_sigs"])})
    if row.get("mutual_friends", 0) > 0:
        reasons.append({"type": "mutual_friends", "count": int(row["mutual_friends"])})
    if row.get("same_affiliation", False):
        aff_val = row.get("affiliation_value", "")
        reasons.append({"type": "same_affiliation", "affiliation": aff_val})
    if row.get("activity_score", 0) > 0.5:
        reasons.append({"type": "activity_recency"})
    return reasons


@celery.task(name="compute_friend_recommendations", bind=True, max_retries=2, default_retry_delay=30)
def compute_friend_recommendations(self: Any) -> dict[str, Any]:
    """Daily Celery Beat task: compute friend recommendations for all users."""
    result: dict[str, Any] = _run_async(_compute_recommendations_async())
    logger.info("Friend recommendation computation complete: %s", result)
    return result


async def _cleanup_dismissed_async() -> int:
    """Remove dismissed recommendations older than retention period.

    Delegates to repo which also cleans up records where the pair became
    friends or where either user was deleted.
    """
    await _ensure_pool()
    from app.core.database import get_pool
    from app.repositories.recommendation_repo import cleanup_stale_dismissed

    pool = get_pool()
    async with pool.acquire() as conn:
        count = await cleanup_stale_dismissed(conn, RECOMMENDATION_DISMISSED_RETENTION_DAYS)
    if count:
        logger.info("Cleaned up %d stale dismissed recommendations", count)
    return count


@celery.task(name="cleanup_dismissed_recommendations")
def cleanup_dismissed_recommendations() -> dict[str, Any]:
    """Weekly cleanup of old dismissed recommendation records."""
    count: int = _run_async(_cleanup_dismissed_async())
    return {"deleted": count}


# ---------------------------------------------------------------------------
# Batched CTE query — compute signals for a batch of users ($1) against
# all other active users. Uses LIMIT $2 per user to cap result set.
# ---------------------------------------------------------------------------
# Signals:
#   S1: Common SIG membership (weight 0.40) — min(count / 3.0, 1.0)
#   S2: Mutual friends (weight 0.35) — min(count / 5.0, 1.0)
#   S3: Same affiliation (weight 0.15) — binary match on LOWER(TRIM(affiliation))
#   S4: Activity recency (weight 0.10) — exp(-0.05 * days_since_last_activity)
# ---------------------------------------------------------------------------
_RECOMMENDATION_BATCH_SQL = """
WITH active_users AS (
    SELECT id, affiliation,
           EXTRACT(EPOCH FROM (NOW() - COALESCE(
               (SELECT MAX(created_at) FROM posts WHERE user_id = u.id AND is_deleted = false),
               u.created_at
           ))) / 86400.0 AS days_inactive
    FROM users u
    WHERE u.is_deleted = false AND u.is_banned = false AND u.role != 'GUEST'
),
batch_users AS (
    SELECT id, affiliation, days_inactive
    FROM active_users
    WHERE id = ANY($1::uuid[])
),
user_pairs AS (
    SELECT a.id AS user_id, b.id AS candidate_id,
           a.affiliation AS user_aff, b.affiliation AS cand_aff,
           b.days_inactive AS cand_days_inactive
    FROM batch_users a
    CROSS JOIN active_users b
    WHERE a.id != b.id
      -- Exclude existing friends (ACCEPTED) AND pending requests
      AND NOT EXISTS (
          SELECT 1 FROM friendships f
          WHERE ((f.requester_id = a.id AND f.addressee_id = b.id)
              OR (f.requester_id = b.id AND f.addressee_id = a.id))
            AND f.status IN ('ACCEPTED', 'PENDING')
      )
      -- Exclude blocked
      AND NOT EXISTS (
          SELECT 1 FROM blocks bl
          WHERE (bl.blocker_id = a.id AND bl.blocked_id = b.id)
             OR (bl.blocker_id = b.id AND bl.blocked_id = a.id)
      )
),
sig_scores AS (
    SELECT up.user_id, up.candidate_id,
           COUNT(DISTINCT sm2.sig_id) AS common_sigs
    FROM user_pairs up
    LEFT JOIN sig_members sm1
        ON sm1.user_id = up.user_id
    LEFT JOIN sig_members sm2
        ON sm2.sig_id = sm1.sig_id
        AND sm2.user_id = up.candidate_id
    GROUP BY up.user_id, up.candidate_id
),
-- Materialise accepted-friendship edges for users involved in this batch only
pair_users AS (
    SELECT DISTINCT uid FROM (
        SELECT user_id AS uid FROM user_pairs
        UNION
        SELECT candidate_id AS uid FROM user_pairs
    ) t
),
user_friends AS (
    SELECT f.requester_id AS uid, f.addressee_id AS friend_id
    FROM friendships f
    JOIN pair_users pu ON pu.uid = f.requester_id
    WHERE f.status = 'ACCEPTED'
    UNION ALL
    SELECT f.addressee_id AS uid, f.requester_id AS friend_id
    FROM friendships f
    JOIN pair_users pu ON pu.uid = f.addressee_id
    WHERE f.status = 'ACCEPTED'
),
friend_scores AS (
    SELECT up.user_id, up.candidate_id,
           COUNT(DISTINCT uf1.friend_id) AS mutual_friends
    FROM user_pairs up
    JOIN user_friends uf1 ON uf1.uid = up.user_id
    JOIN user_friends uf2 ON uf2.uid = up.candidate_id
                          AND uf2.friend_id = uf1.friend_id
    GROUP BY up.user_id, up.candidate_id
),
scored AS (
    SELECT
        up.user_id,
        up.candidate_id,
        COALESCE(ss.common_sigs, 0) AS common_sigs,
        COALESCE(fs.mutual_friends, 0) AS mutual_friends,
        CASE
            WHEN LOWER(TRIM(COALESCE(up.user_aff, ''))) = LOWER(TRIM(COALESCE(up.cand_aff, '')))
                 AND COALESCE(up.user_aff, '') != ''
            THEN 1.0 ELSE 0.0
        END AS same_affiliation,
        CASE
            WHEN LOWER(TRIM(COALESCE(up.user_aff, ''))) = LOWER(TRIM(COALESCE(up.cand_aff, '')))
                 AND COALESCE(up.user_aff, '') != ''
            THEN up.cand_aff ELSE ''
        END AS affiliation_value,
        EXP(-0.05 * up.cand_days_inactive) AS activity_score,
        (
            LEAST(COALESCE(ss.common_sigs, 0) / 3.0, 1.0) * 0.40 +
            LEAST(COALESCE(fs.mutual_friends, 0) / 5.0, 1.0) * 0.35 +
            CASE
                WHEN LOWER(TRIM(COALESCE(up.user_aff, ''))) = LOWER(TRIM(COALESCE(up.cand_aff, '')))
                     AND COALESCE(up.user_aff, '') != ''
                THEN 1.0 ELSE 0.0
            END * 0.15 +
            EXP(-0.05 * up.cand_days_inactive) * 0.10
        ) AS total_score,
        ROW_NUMBER() OVER (PARTITION BY up.user_id ORDER BY (
            LEAST(COALESCE(ss.common_sigs, 0) / 3.0, 1.0) * 0.40 +
            LEAST(COALESCE(fs.mutual_friends, 0) / 5.0, 1.0) * 0.35 +
            CASE
                WHEN LOWER(TRIM(COALESCE(up.user_aff, ''))) = LOWER(TRIM(COALESCE(up.cand_aff, '')))
                     AND COALESCE(up.user_aff, '') != ''
                THEN 1.0 ELSE 0.0
            END * 0.15 +
            EXP(-0.05 * up.cand_days_inactive) * 0.10
        ) DESC) AS rn
    FROM user_pairs up
    LEFT JOIN sig_scores ss
        ON ss.user_id = up.user_id AND ss.candidate_id = up.candidate_id
    LEFT JOIN friend_scores fs
        ON fs.user_id = up.user_id AND fs.candidate_id = up.candidate_id
)
SELECT user_id, candidate_id, common_sigs, mutual_friends,
       same_affiliation, affiliation_value,
       activity_score, total_score
FROM scored
WHERE rn <= $2
ORDER BY user_id, total_score DESC
"""
