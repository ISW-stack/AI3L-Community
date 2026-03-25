"""Celery task: Reconcile all denormalized counters.

Periodically recalculates:
- posts.citation_count from post_citations
- posts.answer_count from comments (for question posts)
- comments.vote_score from comment_votes
- users.profile_view_count_unique from profile_views
- users.profile_view_count_total from profile_views
"""

from typing import Any

from loguru import logger

from app.celery_app import celery
from app.core.database import get_pool
from app.tasks.async_runner import run_async as _run_async
from app.tasks.utils import ensure_pool as _ensure_pool


def _parse_update_count(result: str) -> int:
    """Safely parse the row count from asyncpg's execute() return value.

    asyncpg returns a status string like 'UPDATE N' or 'DELETE N'.
    This function handles unexpected formats gracefully.
    """
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        logger.warning("Unexpected asyncpg result format: %r", result)
        return 0


async def _reconcile_citation_counts() -> int:
    """Recalculate citation_count on all posts from post_citations."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute("""
                UPDATE posts p SET citation_count = sub.cnt
                FROM (
                    SELECT pc.cited_post_id, COUNT(*) AS cnt
                    FROM post_citations pc
                    JOIN posts citing ON pc.citing_post_id = citing.id AND citing.is_deleted = false
                    GROUP BY pc.cited_post_id
                ) sub
                WHERE p.id = sub.cited_post_id AND p.citation_count IS DISTINCT FROM sub.cnt
                """)
            updated = _parse_update_count(result)
            # Also zero out posts with no citations
            await conn.execute("""
                UPDATE posts SET citation_count = 0
                WHERE citation_count > 0
                  AND id NOT IN (
                      SELECT DISTINCT cited_post_id FROM post_citations pc
                      JOIN posts citing ON pc.citing_post_id = citing.id
                        AND citing.is_deleted = false
                  )
                """)
            return updated


async def _reconcile_answer_counts() -> int:
    """Recalculate answer_count on question posts from comments."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute("""
                UPDATE posts p SET answer_count = sub.cnt
                FROM (
                    SELECT c.post_id, COUNT(*) AS cnt
                    FROM comments c
                    WHERE c.parent_id IS NULL AND c.is_deleted = false
                    GROUP BY c.post_id
                ) sub
                WHERE p.id = sub.post_id
                  AND p.type = 'question'
                  AND p.is_deleted = false
                  AND p.answer_count IS DISTINCT FROM sub.cnt
                """)
            updated = _parse_update_count(result)
            # Zero out question posts with no answers
            await conn.execute("""
                UPDATE posts SET answer_count = 0
                WHERE type = 'question' AND answer_count > 0 AND is_deleted = false
                  AND id NOT IN (
                      SELECT DISTINCT post_id FROM comments
                      WHERE parent_id IS NULL AND is_deleted = false
                  )
                """)
            return updated


async def _reconcile_vote_scores() -> int:
    """Recalculate vote_score on comments from comment_votes."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute("""
                UPDATE comments c SET vote_score = COALESCE(sub.total, 0)
                FROM (
                    SELECT comment_id, SUM(vote) AS total
                    FROM comment_votes
                    GROUP BY comment_id
                ) sub
                WHERE c.id = sub.comment_id AND c.vote_score IS DISTINCT FROM COALESCE(sub.total, 0)
                """)
            updated = _parse_update_count(result)
            # Zero out comments with no votes
            await conn.execute("""
                UPDATE comments SET vote_score = 0
                WHERE vote_score != 0
                  AND id NOT IN (SELECT DISTINCT comment_id FROM comment_votes)
                """)
            return updated


async def _reconcile_profile_view_counts() -> tuple[int, int]:
    """Recalculate profile view counts on users from profile_views."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Unique viewers
            result_unique = await conn.execute("""
                UPDATE users u SET profile_view_count_unique = sub.cnt
                FROM (
                    SELECT profile_id, COUNT(DISTINCT viewer_id) AS cnt
                    FROM profile_views
                    GROUP BY profile_id
                ) sub
                WHERE u.id = sub.profile_id
                  AND COALESCE(u.profile_view_count_unique, 0) IS DISTINCT FROM sub.cnt
                """)
            unique_updated = _parse_update_count(result_unique)

            # Total views
            result_total = await conn.execute("""
                UPDATE users u SET profile_view_count_total = sub.cnt
                FROM (
                    SELECT profile_id, SUM(view_count) AS cnt
                    FROM profile_views
                    GROUP BY profile_id
                ) sub
                WHERE u.id = sub.profile_id
                  AND COALESCE(u.profile_view_count_total, 0) IS DISTINCT FROM sub.cnt
                """)
            total_updated = _parse_update_count(result_total)

            return unique_updated, total_updated


@celery.task(name="reconcile_counters", bind=True, max_retries=2, default_retry_delay=30)
def reconcile_counters(self: Any) -> dict[str, Any]:
    """Periodic task: reconcile all denormalized counters."""

    async def _run() -> dict:
        await _ensure_pool()

        citations_updated = await _reconcile_citation_counts()
        answers_updated = await _reconcile_answer_counts()
        votes_updated = await _reconcile_vote_scores()
        unique_updated, total_updated = await _reconcile_profile_view_counts()

        return {
            "citations_updated": citations_updated,
            "answers_updated": answers_updated,
            "votes_updated": votes_updated,
            "profile_views_unique_updated": unique_updated,
            "profile_views_total_updated": total_updated,
        }

    result: dict[str, Any] = _run_async(_run())
    logger.info("Counter reconciliation complete: %s", result)
    return result
