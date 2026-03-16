"""Unit tests for friend recommendations (repo, service, task)."""

import json
import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Celery module mock (must precede imports of app.tasks.*)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _celery_modules():
    """Inject fake celery modules so task imports succeed without a broker."""
    celery_mod = types.ModuleType("celery")
    celery_result_mod = types.ModuleType("celery.result")
    celery_mod.result = celery_result_mod
    celery_mod.shared_task = lambda **kw: (lambda fn: fn)

    celery_app_mod = types.ModuleType("app.celery_app")
    mock_celery_app = MagicMock()
    mock_celery_app.task = lambda *a, **kw: (lambda fn: fn)
    celery_app_mod.celery = mock_celery_app

    saved = {}
    for key in ("celery", "celery.result", "app.celery_app"):
        saved[key] = sys.modules.get(key)

    sys.modules["celery"] = celery_mod
    sys.modules["celery.result"] = celery_result_mod
    sys.modules["app.celery_app"] = celery_app_mod

    yield

    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val

    for mod_name in list(sys.modules):
        if mod_name.startswith("app.tasks."):
            del sys.modules[mod_name]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_rec_row(
    rec_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    recommended_user_id: uuid.UUID | None = None,
    score: float = 0.5,
    reasons: str | list | None = None,
) -> dict:
    """Create a fake recommendation row dict (simulating asyncpg Record)."""
    now = datetime.now(timezone.utc)
    return {
        "id": rec_id or uuid.uuid4(),
        "user_id": user_id or uuid.uuid4(),
        "recommended_user_id": recommended_user_id or uuid.uuid4(),
        "score": score,
        "reasons": reasons or json.dumps([{"type": "common_sig", "count": 2}]),
        "created_at": now,
        "display_name": "Test User",
        "username": "testuser",
        "avatar_url": None,
        "affiliation": "MIT",
    }


# ===========================================================================
# Repository tests
# ===========================================================================


class TestRecommendationRepo:
    """Tests for recommendation_repo functions."""

    @pytest.mark.anyio
    async def test_find_recommendations_empty(self):
        """Returns empty list when no recommendations exist."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        from app.repositories.recommendation_repo import find_recommendations

        result = await find_recommendations(conn, uuid.uuid4())
        assert result == []
        conn.fetch.assert_awaited_once()

    @pytest.mark.anyio
    async def test_find_recommendations_returns_rows(self):
        """Returns recommendation rows ordered by score."""
        uid = uuid.uuid4()
        rows = [_make_rec_row(user_id=uid, score=0.8), _make_rec_row(user_id=uid, score=0.5)]
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=rows)

        from app.repositories.recommendation_repo import find_recommendations

        result = await find_recommendations(conn, uid, limit=10)
        assert len(result) == 2
        # Verify correct params were passed
        call_args = conn.fetch.call_args
        assert call_args[0][1] == uid
        assert call_args[0][2] == 10

    @pytest.mark.anyio
    async def test_dismiss_recommendation(self):
        """Dismiss inserts a row into dismissed_recommendations."""
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        from app.repositories.recommendation_repo import dismiss_recommendation

        uid = uuid.uuid4()
        dismissed_uid = uuid.uuid4()
        await dismiss_recommendation(conn, uid, dismissed_uid)
        conn.execute.assert_awaited_once()

        # Verify the SQL contains ON CONFLICT DO NOTHING
        sql = conn.execute.call_args[0][0]
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql

    @pytest.mark.anyio
    async def test_dismiss_duplicate_no_error(self):
        """Dismissing an already-dismissed user does not raise (ON CONFLICT DO NOTHING)."""
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="INSERT 0 0")

        from app.repositories.recommendation_repo import dismiss_recommendation

        # Should not raise
        await dismiss_recommendation(conn, uuid.uuid4(), uuid.uuid4())
        conn.execute.assert_awaited_once()

    @pytest.mark.anyio
    async def test_delete_all_recommendations(self):
        """delete_all_recommendations executes DELETE statement."""
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="DELETE 5")

        from app.repositories.recommendation_repo import delete_all_recommendations

        await delete_all_recommendations(conn)
        conn.execute.assert_awaited_once()
        sql = conn.execute.call_args[0][0]
        assert "DELETE FROM friend_recommendations" in sql

    @pytest.mark.anyio
    async def test_insert_recommendations_batch_empty(self):
        """insert_recommendations_batch with empty list does nothing."""
        conn = AsyncMock()

        from app.repositories.recommendation_repo import insert_recommendations_batch

        await insert_recommendations_batch(conn, [])
        conn.executemany.assert_not_awaited()

    @pytest.mark.anyio
    async def test_insert_recommendations_batch(self):
        """insert_recommendations_batch calls executemany with correct data."""
        conn = AsyncMock()
        conn.executemany = AsyncMock()

        from app.repositories.recommendation_repo import insert_recommendations_batch

        uid = uuid.uuid4()
        rec_uid = uuid.uuid4()
        rec_id = uuid.uuid4()
        rows = [
            {
                "id": rec_id,
                "user_id": uid,
                "recommended_user_id": rec_uid,
                "score": 0.75,
                "reasons": json.dumps([{"type": "common_sig", "count": 3}]),
            }
        ]
        await insert_recommendations_batch(conn, rows)
        conn.executemany.assert_awaited_once()
        args = conn.executemany.call_args[0]
        assert len(args[1]) == 1
        assert args[1][0][0] == rec_id

    @pytest.mark.anyio
    async def test_count_active_users(self):
        """count_active_users returns the count."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 42})

        from app.repositories.recommendation_repo import count_active_users

        result = await count_active_users(conn)
        assert result == 42

    @pytest.mark.anyio
    async def test_count_active_users_zero(self):
        """count_active_users returns 0 when no active users."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"cnt": 0})

        from app.repositories.recommendation_repo import count_active_users

        result = await count_active_users(conn)
        assert result == 0


# ===========================================================================
# Service tests
# ===========================================================================


class TestRecommendationService:
    """Tests for recommendation service functions."""

    @pytest.mark.anyio
    async def test_get_recommendations_empty(self):
        """Returns empty recommendations list when none exist."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch("app.services.recommendation.get_pool", return_value=mock_pool):
            from app.services.recommendation import get_recommendations

            result = await get_recommendations(str(uuid.uuid4()))

        assert result["recommendations"] == []

    @pytest.mark.anyio
    async def test_get_recommendations_with_data(self):
        """Returns properly formatted recommendations."""
        uid = uuid.uuid4()
        rec_uid = uuid.uuid4()
        rows = [
            _make_rec_row(
                user_id=uid,
                recommended_user_id=rec_uid,
                score=0.75,
                reasons=json.dumps([{"type": "common_sig", "count": 2}]),
            )
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch("app.services.recommendation.get_pool", return_value=mock_pool),
            patch("app.services.recommendation.resolve_avatar_url", return_value=None),
        ):
            from app.services.recommendation import get_recommendations

            result = await get_recommendations(str(uid))

        recs = result["recommendations"]
        assert len(recs) == 1
        assert recs[0]["user_id"] == str(rec_uid)
        assert recs[0]["score"] == 0.75
        assert recs[0]["reasons"] == [{"type": "common_sig", "count": 2}]

    @pytest.mark.anyio
    async def test_get_recommendations_parses_json_string_reasons(self):
        """Reasons stored as JSON string are parsed to list."""
        uid = uuid.uuid4()
        rows = [
            _make_rec_row(
                user_id=uid,
                reasons='[{"type": "mutual_friends", "count": 3}]',
            )
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch("app.services.recommendation.get_pool", return_value=mock_pool),
            patch("app.services.recommendation.resolve_avatar_url", return_value=None),
        ):
            from app.services.recommendation import get_recommendations

            result = await get_recommendations(str(uid))

        assert result["recommendations"][0]["reasons"] == [{"type": "mutual_friends", "count": 3}]

    @pytest.mark.anyio
    async def test_dismiss_recommendation(self):
        """Dismiss calls repo and returns success message."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch("app.services.recommendation.get_pool", return_value=mock_pool):
            from app.services.recommendation import dismiss_recommendation

            result = await dismiss_recommendation(str(uuid.uuid4()), str(uuid.uuid4()))

        assert result["message"] == "Recommendation dismissed"


# ===========================================================================
# Task tests
# ===========================================================================


class TestRecommendationTask:
    """Tests for the compute_friend_recommendations Celery task."""

    @pytest.mark.anyio
    async def test_task_skips_when_few_users(self):
        """Task returns early when fewer than RECOMMENDATION_MIN_USERS."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=5)

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.recommendations import _compute_recommendations_async

            result = await _compute_recommendations_async()

        assert result["skipped"] is True
        assert result["total"] == 0
        # Should not have called fetch (the CTE query)
        mock_conn.fetch.assert_not_awaited()

    @pytest.mark.anyio
    async def test_task_computes_recommendations(self):
        """Task processes rows and inserts recommendations."""
        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()

        cte_rows = [
            {
                "user_id": uid1,
                "candidate_id": uid2,
                "common_sigs": 2,
                "mutual_friends": 1,
                "keyword_similarity": 0.0,
                "same_affiliation": 1.0,
                "affiliation_value": "MIT",
                "activity_score": 0.9,
                "total_score": 0.35,
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=15)
        mock_conn.fetch = AsyncMock(return_value=cte_rows)
        mock_conn.execute = AsyncMock()
        mock_conn.executemany = AsyncMock()

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.recommendations import _compute_recommendations_async

            result = await _compute_recommendations_async()

        assert result["skipped"] is False
        assert result["total"] == 1
        assert result["users"] == 1
        # Verify DELETE was called (clear old recs)
        mock_conn.execute.assert_awaited()
        # Verify executemany was called with the batch
        mock_conn.executemany.assert_awaited()

    @pytest.mark.anyio
    async def test_task_acquires_advisory_lock(self):
        """Task acquires pg_advisory_xact_lock to prevent concurrent execution."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=5)  # Below min users → early return

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.recommendations import _compute_recommendations_async

            await _compute_recommendations_async()

        # Verify advisory lock was acquired
        execute_calls = mock_conn.execute.call_args_list
        assert any(
            "pg_advisory_xact_lock" in str(call) and "compute_recommendations" in str(call)
            for call in execute_calls
        ), f"Expected advisory lock call, got: {execute_calls}"

    @pytest.mark.anyio
    async def test_task_respects_min_score(self):
        """Rows with score below RECOMMENDATION_MIN_SCORE are excluded."""
        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()

        cte_rows = [
            {
                "user_id": uid1,
                "candidate_id": uid2,
                "common_sigs": 0,
                "mutual_friends": 0,
                "keyword_similarity": 0.0,
                "same_affiliation": 0.0,
                "affiliation_value": "",
                "activity_score": 0.01,
                "total_score": 0.001,  # Below RECOMMENDATION_MIN_SCORE
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=15)
        mock_conn.fetch = AsyncMock(return_value=cte_rows)
        mock_conn.execute = AsyncMock()
        mock_conn.executemany = AsyncMock()

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.recommendations import _compute_recommendations_async

            result = await _compute_recommendations_async()

        assert result["total"] == 0


# ===========================================================================
# _build_reasons tests
# ===========================================================================


class TestBuildReasons:
    """Tests for the _build_reasons helper."""

    def test_all_reasons(self):
        """All reason types are included when scores are high."""
        from app.tasks.recommendations import _build_reasons

        row = {
            "common_sigs": 3,
            "mutual_friends": 2,
            "keyword_similarity": 0.5,
            "same_affiliation": True,
            "affiliation_value": "Stanford",
            "activity_score": 0.8,
        }
        reasons = _build_reasons(row)
        reason_types = {r["type"] for r in reasons}
        assert "common_sig" in reason_types
        assert "mutual_friends" in reason_types
        assert "similar_keywords" in reason_types
        assert "same_affiliation" in reason_types
        assert "activity_recency" in reason_types

    def test_no_reasons(self):
        """Empty reasons when all scores are zero."""
        from app.tasks.recommendations import _build_reasons

        row = {
            "common_sigs": 0,
            "mutual_friends": 0,
            "keyword_similarity": 0.0,
            "same_affiliation": False,
            "affiliation_value": "",
            "activity_score": 0.1,
        }
        reasons = _build_reasons(row)
        assert reasons == []

    def test_partial_reasons(self):
        """Only relevant reasons are included."""
        from app.tasks.recommendations import _build_reasons

        row = {
            "common_sigs": 1,
            "mutual_friends": 0,
            "keyword_similarity": 0.0,
            "same_affiliation": False,
            "affiliation_value": "",
            "activity_score": 0.3,
        }
        reasons = _build_reasons(row)
        assert len(reasons) == 1
        assert reasons[0]["type"] == "common_sig"
        assert reasons[0]["count"] == 1


# ===========================================================================
# SQL query structure tests
# ===========================================================================


class TestRecommendationSQL:
    """Tests for the recommendation SQL query structure."""

    def test_sql_has_no_redundant_lateral_join(self):
        """B1: The third redundant LATERAL JOIN (mutual_id re-check) has been removed."""
        from app.tasks.recommendations import _RECOMMENDATION_SQL

        # The SQL should have exactly two LATERAL JOINs (my_friends, their_friends)
        lateral_count = _RECOMMENDATION_SQL.count("LEFT JOIN LATERAL")
        assert (
            lateral_count == 2
        ), f"Expected 2 LATERAL JOINs (my_friends + their_friends), found {lateral_count}"

    def test_sql_counts_my_friend_directly(self):
        """B1: After removing the redundant join, mutual_friends counts my_friends.my_friend."""
        from app.tasks.recommendations import _RECOMMENDATION_SQL

        assert "COUNT(DISTINCT my_friends.my_friend)" in _RECOMMENDATION_SQL

    def test_sql_no_mutual_id_alias(self):
        """B1: The mutual_id alias from the removed third LATERAL JOIN should not exist."""
        from app.tasks.recommendations import _RECOMMENDATION_SQL

        assert "mutual_id" not in _RECOMMENDATION_SQL

    def test_sql_contains_required_ctes(self):
        """The recommendation SQL contains all required CTEs."""
        from app.tasks.recommendations import _RECOMMENDATION_SQL

        assert "active_users AS" in _RECOMMENDATION_SQL
        assert "user_pairs AS" in _RECOMMENDATION_SQL
        assert "sig_scores AS" in _RECOMMENDATION_SQL
        assert "friend_scores AS" in _RECOMMENDATION_SQL

    def test_sql_total_score_formula(self):
        """The total_score calculation uses correct weights summing to 1.0."""
        from app.tasks.recommendations import _RECOMMENDATION_SQL

        assert "* 0.30" in _RECOMMENDATION_SQL  # common_sigs weight
        assert "* 0.25" in _RECOMMENDATION_SQL  # mutual_friends + keyword weights
        assert "* 0.10" in _RECOMMENDATION_SQL  # affiliation + activity weights

    @pytest.mark.anyio
    async def test_task_uses_simplified_sql(self):
        """The task executes the SQL query without error (mock DB)."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=15)
        mock_conn.fetch = AsyncMock(return_value=[])  # No rows
        mock_conn.execute = AsyncMock()

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with (
            patch("app.tasks.cleanup._ensure_pool", new_callable=AsyncMock),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            from app.tasks.recommendations import (
                _RECOMMENDATION_SQL,
                _compute_recommendations_async,
            )

            result = await _compute_recommendations_async()

        assert result["total"] == 0
        assert result["skipped"] is False
        # Verify the correct SQL was passed to conn.fetch
        mock_conn.fetch.assert_awaited_once_with(_RECOMMENDATION_SQL)
