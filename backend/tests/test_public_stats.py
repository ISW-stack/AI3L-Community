"""Tests for public stats endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status


@pytest.fixture
def client():
    """Test client (no auth needed for public endpoints)."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@patch("app.api.v1.endpoints.public.dashboard_repo")
def test_get_public_stats(mock_repo, client):
    # Clear cache
    from app.api.v1.endpoints.public import _stats_cache

    _stats_cache.clear()

    mock_repo.count_users = AsyncMock(return_value=42)
    mock_repo.count_posts = AsyncMock(return_value=100)
    mock_repo.count_sigs = AsyncMock(return_value=5)

    resp = client.get("/api/v1/public/stats")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["member_count"] == 42
    assert data["post_count"] == 100
    assert data["sig_count"] == 5


@patch("app.api.v1.endpoints.public.dashboard_repo")
def test_public_stats_cache(mock_repo, client):
    """Second call should use cached data."""
    from app.api.v1.endpoints.public import _stats_cache

    _stats_cache.clear()

    mock_repo.count_users = AsyncMock(return_value=10)
    mock_repo.count_posts = AsyncMock(return_value=20)
    mock_repo.count_sigs = AsyncMock(return_value=3)

    # First call
    resp1 = client.get("/api/v1/public/stats")
    assert resp1.status_code == 200

    # Second call - should use cache
    mock_repo.count_users = AsyncMock(return_value=999)
    resp2 = client.get("/api/v1/public/stats")
    assert resp2.status_code == 200
    # Should still be 10, not 999 (cached)
    assert resp2.json()["member_count"] == 10


@patch("app.api.v1.endpoints.public.dashboard_repo")
def test_public_stats_no_auth_required(mock_repo, client):
    """Endpoint should work without any auth headers."""
    from app.api.v1.endpoints.public import _stats_cache

    _stats_cache.clear()

    mock_repo.count_users = AsyncMock(return_value=1)
    mock_repo.count_posts = AsyncMock(return_value=2)
    mock_repo.count_sigs = AsyncMock(return_value=3)

    resp = client.get("/api/v1/public/stats")
    assert resp.status_code == 200


@patch("app.api.v1.endpoints.public.dashboard_repo")
def test_public_stats_returns_correct_shape(mock_repo, client):
    """Response must have exactly the expected keys — no internal keys like _ts."""
    from app.api.v1.endpoints.public import _stats_cache

    _stats_cache.clear()

    mock_repo.count_users = AsyncMock(return_value=7)
    mock_repo.count_posts = AsyncMock(return_value=14)
    mock_repo.count_sigs = AsyncMock(return_value=2)

    resp = client.get("/api/v1/public/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"member_count", "post_count", "sig_count"}
    assert "_ts" not in data


@patch("app.api.v1.endpoints.public.time")
@patch("app.api.v1.endpoints.public.dashboard_repo")
def test_public_stats_cache_expires_after_ttl(mock_repo, mock_time, client):
    """Cache should expire after TTL (300s), forcing a fresh repo call."""
    from app.api.v1.endpoints.public import _stats_cache

    _stats_cache.clear()

    mock_time.monotonic.return_value = 1000.0

    mock_repo.count_users = AsyncMock(return_value=10)
    mock_repo.count_posts = AsyncMock(return_value=20)
    mock_repo.count_sigs = AsyncMock(return_value=3)

    # First call populates cache at t=1000
    resp1 = client.get("/api/v1/public/stats")
    assert resp1.status_code == 200
    assert resp1.json()["member_count"] == 10
    # Second call within TTL — should use cache
    mock_time.monotonic.return_value = 1200.0  # +200s < 300s TTL
    mock_repo.count_users = AsyncMock(return_value=999)
    mock_repo.count_posts = AsyncMock(return_value=888)
    mock_repo.count_sigs = AsyncMock(return_value=777)

    resp2 = client.get("/api/v1/public/stats")
    assert resp2.status_code == 200
    assert resp2.json()["member_count"] == 10  # Still cached

    # Third call after TTL expires — should hit repo again
    mock_time.monotonic.return_value = 1301.0  # +301s > 300s TTL
    resp3 = client.get("/api/v1/public/stats")
    assert resp3.status_code == 200
    assert resp3.json()["member_count"] == 999  # Fresh data


@patch("app.api.v1.endpoints.public.dashboard_repo")
def test_public_stats_repo_error_raises(mock_repo, client):
    """If a repo function raises, endpoint should propagate the error (500)."""
    from app.api.v1.endpoints.public import _stats_cache

    _stats_cache.clear()

    mock_repo.count_users = AsyncMock(side_effect=RuntimeError("DB connection failed"))
    mock_repo.count_posts = AsyncMock(return_value=0)
    mock_repo.count_sigs = AsyncMock(return_value=0)

    with pytest.raises((RuntimeError, ExceptionGroup)):
        client.get("/api/v1/public/stats")


@patch("app.api.v1.endpoints.public.dashboard_repo")
def test_public_stats_returns_zero_counts(mock_repo, client):
    """Zero counts should be returned as 0, not as errors."""
    from app.api.v1.endpoints.public import _stats_cache

    _stats_cache.clear()

    mock_repo.count_users = AsyncMock(return_value=0)
    mock_repo.count_posts = AsyncMock(return_value=0)
    mock_repo.count_sigs = AsyncMock(return_value=0)

    resp = client.get("/api/v1/public/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["member_count"] == 0
    assert data["post_count"] == 0
    assert data["sig_count"] == 0
