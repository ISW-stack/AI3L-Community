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
