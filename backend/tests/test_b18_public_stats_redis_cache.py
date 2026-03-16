"""B18: Public stats uses Redis-based cache instead of per-process in-memory cache."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

_RL = "app.api.v1.endpoints.public.check_rate_limit"
_REDIS = "app.api.v1.endpoints.public.get_redis"
_REPO = "app.api.v1.endpoints.public.dashboard_repo"


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def sync_client(mock_redis_client):
    """Sync test client with rate limiting and Redis mocked."""
    from fastapi.testclient import TestClient

    from app.main import app

    with (
        patch(_RL, new_callable=AsyncMock, return_value=True),
        patch(_REDIS, return_value=mock_redis_client),
    ):
        yield TestClient(app)


class TestRedisCache:
    """Public stats endpoint uses Redis for cross-worker caching."""

    @patch(_REPO)
    def test_cache_miss_fetches_from_repo_and_sets_redis(
        self, mock_repo, mock_redis_client
    ):
        """On cache miss (Redis returns None), fetch from repo and store in Redis."""
        from fastapi.testclient import TestClient

        from app.main import app

        mock_redis_client.get.return_value = None
        mock_repo.count_users = AsyncMock(return_value=42)
        mock_repo.count_posts = AsyncMock(return_value=100)
        mock_repo.count_sigs = AsyncMock(return_value=5)

        with (
            patch(_RL, new_callable=AsyncMock, return_value=True),
            patch(_REDIS, return_value=mock_redis_client),
        ):
            client = TestClient(app)
            resp = client.get("/api/v1/public/stats")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["member_count"] == 42
        assert data["post_count"] == 100
        assert data["sig_count"] == 5

        # Verify Redis set was called with correct key and TTL
        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[0][0] == "public:stats"
        stored = json.loads(call_args[0][1])
        assert stored["member_count"] == 42
        assert call_args[1]["ex"] == 300

    @patch(_REPO)
    def test_cache_hit_returns_cached_data(self, mock_repo):
        """On cache hit, return data from Redis without querying repo."""
        from fastapi.testclient import TestClient

        from app.main import app

        cached_data = json.dumps(
            {"member_count": 10, "post_count": 20, "sig_count": 3}
        )
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=cached_data)
        redis.set = AsyncMock()

        # These should NOT be called
        mock_repo.count_users = AsyncMock(return_value=999)
        mock_repo.count_posts = AsyncMock(return_value=999)
        mock_repo.count_sigs = AsyncMock(return_value=999)

        with (
            patch(_RL, new_callable=AsyncMock, return_value=True),
            patch(_REDIS, return_value=redis),
        ):
            client = TestClient(app)
            resp = client.get("/api/v1/public/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["member_count"] == 10
        assert data["post_count"] == 20
        assert data["sig_count"] == 3

        # Repo should NOT have been called
        mock_repo.count_users.assert_not_called()
        mock_repo.count_posts.assert_not_called()
        mock_repo.count_sigs.assert_not_called()

        # Redis set should NOT have been called (cache hit)
        redis.set.assert_not_called()

    def test_no_internal_keys_in_response(self, mock_redis_client):
        """Response should not contain _ts or any internal cache keys."""
        from fastapi.testclient import TestClient

        from app.main import app

        cached_data = json.dumps(
            {"member_count": 7, "post_count": 14, "sig_count": 2}
        )
        mock_redis_client.get.return_value = cached_data

        with (
            patch(_RL, new_callable=AsyncMock, return_value=True),
            patch(_REDIS, return_value=mock_redis_client),
        ):
            client = TestClient(app)
            resp = client.get("/api/v1/public/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"member_count", "post_count", "sig_count"}
        assert "_ts" not in data

    @patch(_REPO)
    def test_zero_counts_returned_correctly(self, mock_repo, mock_redis_client):
        """Zero counts from repo should be returned as 0."""
        from fastapi.testclient import TestClient

        from app.main import app

        mock_redis_client.get.return_value = None
        mock_repo.count_users = AsyncMock(return_value=0)
        mock_repo.count_posts = AsyncMock(return_value=0)
        mock_repo.count_sigs = AsyncMock(return_value=0)

        with (
            patch(_RL, new_callable=AsyncMock, return_value=True),
            patch(_REDIS, return_value=mock_redis_client),
        ):
            client = TestClient(app)
            resp = client.get("/api/v1/public/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["member_count"] == 0
        assert data["post_count"] == 0
        assert data["sig_count"] == 0

    @patch(_REPO)
    def test_repo_error_propagates(self, mock_repo, mock_redis_client):
        """If repo raises, the error should propagate (500)."""
        from fastapi.testclient import TestClient

        from app.main import app

        mock_redis_client.get.return_value = None
        mock_repo.count_users = AsyncMock(
            side_effect=RuntimeError("DB connection failed")
        )
        mock_repo.count_posts = AsyncMock(return_value=0)
        mock_repo.count_sigs = AsyncMock(return_value=0)

        with (
            patch(_RL, new_callable=AsyncMock, return_value=True),
            patch(_REDIS, return_value=mock_redis_client),
        ):
            client = TestClient(app)
            with pytest.raises((RuntimeError, ExceptionGroup)):
                client.get("/api/v1/public/stats")

    def test_no_auth_required(self, mock_redis_client):
        """Endpoint should work without any auth headers."""
        from fastapi.testclient import TestClient

        from app.main import app

        cached_data = json.dumps(
            {"member_count": 1, "post_count": 2, "sig_count": 3}
        )
        mock_redis_client.get.return_value = cached_data

        with (
            patch(_RL, new_callable=AsyncMock, return_value=True),
            patch(_REDIS, return_value=mock_redis_client),
        ):
            client = TestClient(app)
            resp = client.get("/api/v1/public/stats")

        assert resp.status_code == 200

    @patch(_REPO)
    def test_cache_key_is_public_stats(self, mock_repo, mock_redis_client):
        """The Redis cache key should be 'public:stats'."""
        from fastapi.testclient import TestClient

        from app.main import app

        mock_redis_client.get.return_value = None
        mock_repo.count_users = AsyncMock(return_value=1)
        mock_repo.count_posts = AsyncMock(return_value=2)
        mock_repo.count_sigs = AsyncMock(return_value=3)

        with (
            patch(_RL, new_callable=AsyncMock, return_value=True),
            patch(_REDIS, return_value=mock_redis_client),
        ):
            client = TestClient(app)
            client.get("/api/v1/public/stats")

        # Verify Redis.get was called with the correct key
        mock_redis_client.get.assert_called_once_with("public:stats")
