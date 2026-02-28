from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncClient:
    """Create a test client without triggering lifespan (no DB/Redis needed)."""
    from app.main import app

    # Patch lifespan dependencies so no real connections are made
    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock) as _mock_db,
        patch("app.main.init_redis", new_callable=AsyncMock) as _mock_redis,
        patch("app.main.close_db_pool", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
