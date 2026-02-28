from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient


@patch("app.api.v1.endpoints.health.get_redis")
@patch("app.api.v1.endpoints.health.get_pool")
async def test_health_check_healthy(
    mock_get_pool: MagicMock,
    mock_get_redis: MagicMock,
    client: AsyncClient,
) -> None:
    # Mock PostgreSQL
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_pool = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_get_pool.return_value = mock_pool

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_get_redis.return_value = mock_redis

    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert len(data["dependencies"]) == 2
    assert data["dependencies"][0]["name"] == "postgresql"
    assert data["dependencies"][1]["name"] == "redis"
