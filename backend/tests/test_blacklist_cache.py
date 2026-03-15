"""Tests for app.core.blacklist — Redis block cache helpers."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.blacklist import (
    build_block_exclusion_clause,
    get_blocked_user_ids,
    update_block_cache,
    warmup_block_cache,
)


class TestGetBlockedUserIds:
    async def test_returns_set_from_redis(self):
        redis = AsyncMock()
        user_id = str(uuid.uuid4())
        blocked_1 = str(uuid.uuid4())
        blocked_2 = str(uuid.uuid4())
        redis.smembers.return_value = {blocked_1, blocked_2}

        result = await get_blocked_user_ids(redis, user_id)
        assert result == {blocked_1, blocked_2}
        redis.smembers.assert_called_once_with(f"block:set:{user_id}")

    async def test_returns_empty_on_cache_miss(self):
        redis = AsyncMock()
        redis.smembers.return_value = set()

        result = await get_blocked_user_ids(redis, str(uuid.uuid4()))
        assert result == set()

    async def test_decodes_bytes(self):
        redis = AsyncMock()
        uid = str(uuid.uuid4())
        redis.smembers.return_value = {uid.encode()}

        result = await get_blocked_user_ids(redis, str(uuid.uuid4()))
        assert result == {uid}


class TestWarmupBlockCache:
    async def test_loads_all_blocks(self, mock_pool, mock_conn):
        blocker = uuid.uuid4()
        blocked = uuid.uuid4()
        mock_conn.fetch.return_value = [
            {"blocker_id": blocker, "blocked_id": blocked},
        ]

        pipe = MagicMock()
        pipe.sadd = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[])
        redis = MagicMock()
        redis.pipeline = MagicMock(return_value=pipe)

        await warmup_block_cache(mock_pool, redis)
        assert pipe.sadd.call_count == 2  # bilateral
        pipe.execute.assert_called_once()

    async def test_no_blocks_noop(self, mock_pool, mock_conn):
        mock_conn.fetch.return_value = []

        redis = MagicMock()
        await warmup_block_cache(mock_pool, redis)
        redis.pipeline.assert_not_called()


class TestUpdateBlockCache:
    async def test_add_block(self):
        pipe = MagicMock()
        pipe.sadd = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[])
        redis = MagicMock()
        redis.pipeline = MagicMock(return_value=pipe)

        blocker = str(uuid.uuid4())
        blocked = str(uuid.uuid4())
        await update_block_cache(redis, blocker, blocked, added=True)
        assert pipe.sadd.call_count == 2

    async def test_remove_block(self):
        pipe = MagicMock()
        pipe.srem = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[])
        redis = MagicMock()
        redis.pipeline = MagicMock(return_value=pipe)

        blocker = str(uuid.uuid4())
        blocked = str(uuid.uuid4())
        await update_block_cache(redis, blocker, blocked, added=False)
        assert pipe.srem.call_count == 2


class TestBuildBlockExclusionClause:
    def test_returns_correct_sql(self):
        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        sql, params = build_block_exclusion_clause({uid1, uid2}, "p.user_id", 3)
        assert "p.user_id != ALL($3::uuid[])" in sql
        assert len(params) == 1
        assert len(params[0]) == 2  # two UUIDs

    def test_empty_set_returns_empty(self):
        sql, params = build_block_exclusion_clause(set(), "p.user_id", 3)
        assert sql == ""
        assert params == []

    def test_rejects_invalid_column(self):
        with pytest.raises(ValueError, match="Invalid column"):
            build_block_exclusion_clause({str(uuid.uuid4())}, "evil_column", 1)

    def test_all_allowed_columns(self):
        allowed = [
            "p.user_id",
            "cm.user_id",
            "n.trigger_user_id",
            "f.created_by",
            "ap.uploaded_by",
            "ac.user_id",
            "fr.user_id",
        ]
        uid = str(uuid.uuid4())
        for col in allowed:
            sql, params = build_block_exclusion_clause({uid}, col, 1)
            assert col in sql
