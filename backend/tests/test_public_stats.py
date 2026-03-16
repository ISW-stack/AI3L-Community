"""Tests for public stats endpoint (Redis-based cache)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

_RL = "app.api.v1.endpoints.public.check_rate_limit"
_REDIS = "app.api.v1.endpoints.public.get_redis"
_REPO = "app.api.v1.endpoints.public.dashboard_repo"


def _make_redis(cached: str | None = None) -> AsyncMock:
    """Create a mock Redis client, optionally pre-loaded with cached data."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=cached)
    redis.set = AsyncMock(return_value=True)
    return redis


def _make_client(redis_mock: AsyncMock):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app), redis_mock


@patch(_REPO)
def test_get_public_stats(mock_repo):
    """Cache miss: fetches from repo, stores in Redis, returns data."""
    redis = _make_redis(None)
    mock_repo.count_users = AsyncMock(return_value=42)
    mock_repo.count_posts = AsyncMock(return_value=100)
    mock_repo.count_sigs = AsyncMock(return_value=5)

    with (
        patch(_RL, new_callable=AsyncMock, return_value=True),
        patch(_REDIS, return_value=redis),
    ):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/public/stats")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["member_count"] == 42
    assert data["post_count"] == 100
    assert data["sig_count"] == 5


@patch(_REPO)
def test_public_stats_cache(mock_repo):
    """Second call should use cached data from Redis."""
    cached = json.dumps({"member_count": 10, "post_count": 20, "sig_count": 3})
    redis = _make_redis(cached)

    mock_repo.count_users = AsyncMock(return_value=999)
    mock_repo.count_posts = AsyncMock(return_value=999)
    mock_repo.count_sigs = AsyncMock(return_value=999)

    with (
        patch(_RL, new_callable=AsyncMock, return_value=True),
        patch(_REDIS, return_value=redis),
    ):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/public/stats")
    assert resp.status_code == 200
    assert resp.json()["member_count"] == 10
    # Repo should not have been called
    mock_repo.count_users.assert_not_called()


@patch(_REPO)
def test_public_stats_no_auth_required(mock_repo):
    """Endpoint should work without any auth headers."""
    redis = _make_redis(None)
    mock_repo.count_users = AsyncMock(return_value=1)
    mock_repo.count_posts = AsyncMock(return_value=2)
    mock_repo.count_sigs = AsyncMock(return_value=3)

    with (
        patch(_RL, new_callable=AsyncMock, return_value=True),
        patch(_REDIS, return_value=redis),
    ):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/public/stats")
    assert resp.status_code == 200


@patch(_REPO)
def test_public_stats_returns_correct_shape(mock_repo):
    """Response must have exactly the expected keys — no internal keys like _ts."""
    redis = _make_redis(None)
    mock_repo.count_users = AsyncMock(return_value=7)
    mock_repo.count_posts = AsyncMock(return_value=14)
    mock_repo.count_sigs = AsyncMock(return_value=2)

    with (
        patch(_RL, new_callable=AsyncMock, return_value=True),
        patch(_REDIS, return_value=redis),
    ):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/public/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"member_count", "post_count", "sig_count"}
    assert "_ts" not in data


@patch(_REPO)
def test_public_stats_repo_error_raises(mock_repo):
    """If a repo function raises, endpoint should propagate the error (500)."""
    redis = _make_redis(None)
    mock_repo.count_users = AsyncMock(side_effect=RuntimeError("DB connection failed"))
    mock_repo.count_posts = AsyncMock(return_value=0)
    mock_repo.count_sigs = AsyncMock(return_value=0)

    with (
        patch(_RL, new_callable=AsyncMock, return_value=True),
        patch(_REDIS, return_value=redis),
    ):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        with pytest.raises((RuntimeError, ExceptionGroup)):
            client.get("/api/v1/public/stats")


@patch(_REPO)
def test_public_stats_returns_zero_counts(mock_repo):
    """Zero counts should be returned as 0, not as errors."""
    redis = _make_redis(None)
    mock_repo.count_users = AsyncMock(return_value=0)
    mock_repo.count_posts = AsyncMock(return_value=0)
    mock_repo.count_sigs = AsyncMock(return_value=0)

    with (
        patch(_RL, new_callable=AsyncMock, return_value=True),
        patch(_REDIS, return_value=redis),
    ):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/public/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["member_count"] == 0
    assert data["post_count"] == 0
    assert data["sig_count"] == 0
