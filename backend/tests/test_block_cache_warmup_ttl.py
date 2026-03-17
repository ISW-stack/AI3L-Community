"""Tests for block cache warmup TTL (N-B08 fix)."""

import uuid
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.core.blacklist import warmup_block_cache


class TestWarmupBlockCacheTTL:
    async def test_expire_called_for_each_unique_key(self, mock_pool, mock_conn):
        """warmup_block_cache sets 24h TTL on every block:set:* key."""
        blocker1 = uuid.uuid4()
        blocked1 = uuid.uuid4()
        blocker2 = uuid.uuid4()
        blocked2 = uuid.uuid4()
        mock_conn.fetch.return_value = [
            {"blocker_id": blocker1, "blocked_id": blocked1},
            {"blocker_id": blocker2, "blocked_id": blocked2},
        ]

        pipe = MagicMock()
        pipe.sadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[])
        redis = MagicMock()
        redis.pipeline = MagicMock(return_value=pipe)

        await warmup_block_cache(mock_pool, redis)

        # 4 sadd calls (2 per row, bilateral)
        assert pipe.sadd.call_count == 4

        # expire called for each unique key — 4 unique users = 4 keys
        expire_calls = pipe.expire.call_args_list
        assert len(expire_calls) == 4
        # All expire calls use 86400 (24h)
        for call in expire_calls:
            assert call[0][1] == 86400

    async def test_expire_deduplicates_keys(self, mock_pool, mock_conn):
        """warmup_block_cache only calls expire once per unique key even with multiple rows."""
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        user_c = uuid.uuid4()
        # user_a blocks both user_b and user_c
        mock_conn.fetch.return_value = [
            {"blocker_id": user_a, "blocked_id": user_b},
            {"blocker_id": user_a, "blocked_id": user_c},
        ]

        pipe = MagicMock()
        pipe.sadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[])
        redis = MagicMock()
        redis.pipeline = MagicMock(return_value=pipe)

        await warmup_block_cache(mock_pool, redis)

        # 3 unique keys: block:set:{user_a}, block:set:{user_b}, block:set:{user_c}
        expire_calls = pipe.expire.call_args_list
        assert len(expire_calls) == 3

        expire_keys = {call[0][0] for call in expire_calls}
        assert f"block:set:{user_a}" in expire_keys
        assert f"block:set:{user_b}" in expire_keys
        assert f"block:set:{user_c}" in expire_keys

    async def test_no_expire_when_no_blocks(self, mock_pool, mock_conn):
        """warmup_block_cache does nothing when there are no blocks."""
        mock_conn.fetch.return_value = []

        redis = MagicMock()
        await warmup_block_cache(mock_pool, redis)
        redis.pipeline.assert_not_called()
