"""Daily friend recommendation computation task."""

import json
import uuid
from typing import Any

from loguru import logger

from app.celery_app import celery
from app.core.constants import (
    RECOMMENDATION_BATCH_SIZE,
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

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Try to acquire advisory lock; skip if another task is already running.
            # pg_try_advisory_xact_lock returns false if lock is held elsewhere.
            lock_acquired = await conn.fetchval(
                "SELECT pg_try_advisory_xact_lock(hashtext('compute_recommendations'))"
            )
            if not lock_acquired:
                logger.info(
                    "Skipping recommendation recompute — another task holds the lock"
                )
                return {"total": 0, "users": 0, "skipped": True, "reason": "lock_held"}

            # Check minimum user count
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

            # Clear old recommendations before writing new ones
            await conn.execute("DELETE FROM friend_recommendations")

            # Fetch all active user IDs for batching
            user_ids = [
                row["id"]
                for row in await conn.fetch(
                    "SELECT id FROM users "
                    "WHERE is_deleted = false AND is_banned = false AND role != 'GUEST' "
                    "ORDER BY id"
                )
            ]

            total = 0
            users_with_recs = 0

            # Process users in batches to avoid O(N^2) memory usage
            for batch_start in range(0, len(user_ids), RECOMMENDATION_BATCH_SIZE):
                batch = user_ids[batch_start : batch_start + RECOMMENDATION_BATCH_SIZE]

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

                for recs in user_recs.values():
                    if recs:
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
                                for r in recs
                            ],
                        )

                batch_total = sum(len(r) for r in user_recs.values())
                total += batch_total
                users_with_recs += len(user_recs)

            logger.info("Computed %d recommendations for %d users", total, users_with_recs)
            return {"total": total, "users": users_with_recs, "skipped": False}


def _build_reasons(row: Any) -> list[dict[str, Any]]:
    """Build structured reasons list from score components."""
    reasons: list[dict[str, Any]] = []
    if row.get("common_sigs", 0) > 0:
        reasons.append({"type": "common_sig", "count": int(row["common_sigs"])})
    if row.get("mutual_friends", 0) > 0:
        reasons.append({"type": "mutual_friends", "count": int(row["mutual_friends"])})
    if row.get("keyword_similarity", 0) > 0.01:
        reasons.append({"type": "similar_keywords"})
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


# ---------------------------------------------------------------------------
# Batched CTE query — compute signals for a batch of users ($1) against
# all other active users. Uses LIMIT $2 per user to cap result set.
# ---------------------------------------------------------------------------
# Signals:
#   S1: Common SIG membership (weight 0.30) — min(count / 3.0, 1.0)
#   S2: Mutual friends (weight 0.25) — min(count / 5.0, 1.0)
#   S3: Similar keywords (weight 0.25) — placeholder 0.0 (Jaccard)
#   S4: Same affiliation (weight 0.10) — binary match on LOWER(TRIM(affiliation))
#   S5: Activity recency (weight 0.10) — exp(-0.05 * days_since_last_activity)
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
      -- Exclude existing friends
      AND NOT EXISTS (
          SELECT 1 FROM friendships f
          WHERE f.status = 'ACCEPTED'
            AND ((f.requester_id = a.id AND f.addressee_id = b.id)
              OR (f.requester_id = b.id AND f.addressee_id = a.id))
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
friend_scores AS (
    SELECT up.user_id, up.candidate_id,
           COUNT(DISTINCT my_friends.my_friend) AS mutual_friends
    FROM user_pairs up
    LEFT JOIN LATERAL (
        SELECT CASE
            WHEN f1.requester_id = up.user_id THEN f1.addressee_id
            ELSE f1.requester_id
        END AS my_friend
        FROM friendships f1
        WHERE f1.status = 'ACCEPTED'
          AND (f1.requester_id = up.user_id OR f1.addressee_id = up.user_id)
    ) my_friends ON true
    LEFT JOIN LATERAL (
        SELECT CASE
            WHEN f2.requester_id = up.candidate_id THEN f2.addressee_id
            ELSE f2.requester_id
        END AS their_friend
        FROM friendships f2
        WHERE f2.status = 'ACCEPTED'
          AND (f2.requester_id = up.candidate_id OR f2.addressee_id = up.candidate_id)
    ) their_friends ON my_friends.my_friend = their_friends.their_friend
    GROUP BY up.user_id, up.candidate_id
),
scored AS (
    SELECT
        up.user_id,
        up.candidate_id,
        COALESCE(ss.common_sigs, 0) AS common_sigs,
        COALESCE(fs.mutual_friends, 0) AS mutual_friends,
        0.0 AS keyword_similarity,
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
            LEAST(COALESCE(ss.common_sigs, 0) / 3.0, 1.0) * 0.30 +
            LEAST(COALESCE(fs.mutual_friends, 0) / 5.0, 1.0) * 0.25 +
            0.0 * 0.25 +
            CASE
                WHEN LOWER(TRIM(COALESCE(up.user_aff, ''))) = LOWER(TRIM(COALESCE(up.cand_aff, '')))
                     AND COALESCE(up.user_aff, '') != ''
                THEN 1.0 ELSE 0.0
            END * 0.10 +
            EXP(-0.05 * up.cand_days_inactive) * 0.10
        ) AS total_score,
        ROW_NUMBER() OVER (PARTITION BY up.user_id ORDER BY (
            LEAST(COALESCE(ss.common_sigs, 0) / 3.0, 1.0) * 0.30 +
            LEAST(COALESCE(fs.mutual_friends, 0) / 5.0, 1.0) * 0.25 +
            0.0 * 0.25 +
            CASE
                WHEN LOWER(TRIM(COALESCE(up.user_aff, ''))) = LOWER(TRIM(COALESCE(up.cand_aff, '')))
                     AND COALESCE(up.user_aff, '') != ''
                THEN 1.0 ELSE 0.0
            END * 0.10 +
            EXP(-0.05 * up.cand_days_inactive) * 0.10
        ) DESC) AS rn
    FROM user_pairs up
    LEFT JOIN sig_scores ss
        ON ss.user_id = up.user_id AND ss.candidate_id = up.candidate_id
    LEFT JOIN friend_scores fs
        ON fs.user_id = up.user_id AND fs.candidate_id = up.candidate_id
)
SELECT user_id, candidate_id, common_sigs, mutual_friends,
       keyword_similarity, same_affiliation, affiliation_value,
       activity_score, total_score
FROM scored
WHERE rn <= $2
ORDER BY user_id, total_score DESC
"""
