"""Daily friend recommendation computation task."""

import json
import uuid
from typing import Any

from loguru import logger

from app.celery_app import celery
from app.core.config import settings
from app.core.constants import (
    RECOMMENDATION_MAX_PER_USER,
    RECOMMENDATION_MIN_SCORE,
    RECOMMENDATION_MIN_USERS,
)
from app.tasks.cleanup import _ensure_pool, _run_async


async def _compute_recommendations_async() -> dict[str, int]:
    """Async implementation of recommendation computation."""
    await _ensure_pool()

    from app.core.database import get_pool

    pool = get_pool()

    async with pool.acquire() as conn:
        # Check minimum user count
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM users "
            "WHERE is_deleted = false AND is_banned = false AND role != 'GUEST'"
        )
        if count < RECOMMENDATION_MIN_USERS:
            logger.info("Not enough users (%d) for recommendations", count)
            return {"total": 0, "users": 0, "skipped": True}

        # Compute recommendations using CTE-based SQL
        rows = await conn.fetch(_RECOMMENDATION_SQL)

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

        # Write results in transaction
        async with conn.transaction():
            await conn.execute("DELETE FROM friend_recommendations")
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

        total = sum(len(r) for r in user_recs.values())
        logger.info(
            "Computed %d recommendations for %d users", total, len(user_recs)
        )
        return {"total": total, "users": len(user_recs), "skipped": False}


def _build_reasons(row: Any) -> list[dict[str, Any]]:
    """Build structured reasons list from score components."""
    reasons: list[dict[str, Any]] = []
    if row.get("common_sigs", 0) > 0:
        reasons.append({"type": "common_sig", "count": int(row["common_sigs"])})
    if row.get("mutual_friends", 0) > 0:
        reasons.append(
            {"type": "mutual_friends", "count": int(row["mutual_friends"])}
        )
    if row.get("keyword_similarity", 0) > 0.01:
        reasons.append({"type": "similar_keywords"})
    if row.get("same_affiliation", False):
        aff_val = row.get("affiliation_value", "")
        reasons.append({"type": "same_affiliation", "affiliation": aff_val})
    if row.get("activity_score", 0) > 0.5:
        reasons.append({"type": "activity_recency"})
    return reasons


@celery.task(name="compute_friend_recommendations", bind=True, max_retries=1)
def compute_friend_recommendations(self: Any) -> dict[str, Any]:
    """Daily Celery Beat task: compute friend recommendations for all users."""
    result: dict[str, Any] = _run_async(_compute_recommendations_async())
    logger.info("Friend recommendation computation complete: %s", result)
    return result


# ---------------------------------------------------------------------------
# Large CTE query — compute all signals between all user pairs
# ---------------------------------------------------------------------------
# Signals:
#   S1: Common SIG membership (weight 0.30) — min(count / 3.0, 1.0)
#   S2: Mutual friends (weight 0.25) — min(count / 5.0, 1.0)
#   S3: Similar keywords (weight 0.25) — placeholder 0.0 (Jaccard)
#   S4: Same affiliation (weight 0.10) — binary match on LOWER(TRIM(affiliation))
#   S5: Activity recency (weight 0.10) — exp(-0.05 * days_since_last_activity)
# ---------------------------------------------------------------------------
_RECOMMENDATION_SQL = """
WITH active_users AS (
    SELECT id, affiliation,
           EXTRACT(EPOCH FROM (NOW() - COALESCE(
               (SELECT MAX(created_at) FROM posts WHERE user_id = u.id AND is_deleted = false),
               u.created_at
           ))) / 86400.0 AS days_inactive
    FROM users u
    WHERE u.is_deleted = false AND u.is_banned = false AND u.role != 'GUEST'
),
user_pairs AS (
    SELECT a.id AS user_id, b.id AS candidate_id,
           a.affiliation AS user_aff, b.affiliation AS cand_aff,
           b.days_inactive AS cand_days_inactive
    FROM active_users a
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
        ON sm1.user_id = up.user_id AND sm1.status = 'ACCEPTED'
    LEFT JOIN sig_members sm2
        ON sm2.sig_id = sm1.sig_id
        AND sm2.user_id = up.candidate_id
        AND sm2.status = 'ACCEPTED'
    GROUP BY up.user_id, up.candidate_id
),
friend_scores AS (
    SELECT up.user_id, up.candidate_id,
           COUNT(DISTINCT mutual_id) AS mutual_friends
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
    LEFT JOIN LATERAL (
        SELECT my_friends.my_friend AS mutual_id
        WHERE my_friends.my_friend = their_friends.their_friend
    ) m ON true
    GROUP BY up.user_id, up.candidate_id
)
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
    ) AS total_score
FROM user_pairs up
LEFT JOIN sig_scores ss
    ON ss.user_id = up.user_id AND ss.candidate_id = up.candidate_id
LEFT JOIN friend_scores fs
    ON fs.user_id = up.user_id AND fs.candidate_id = up.candidate_id
ORDER BY up.user_id, total_score DESC
"""
