import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


_TEST_CSRF_TOKEN = "test-csrf-token"


@pytest.fixture
async def client() -> AsyncClient:
    """Create a test client without triggering lifespan (no DB/Redis needed).

    Includes CSRF cookie + header by default so tests pass through CSRF middleware.
    """
    from app.main import app

    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"csrf_token": _TEST_CSRF_TOKEN},
            headers={"X-CSRF-Token": _TEST_CSRF_TOKEN},
        ) as ac:
            yield ac


@pytest.fixture
def mock_conn():
    """Mock asyncpg connection with fetchrow, fetch, fetchval, execute, transaction."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock(return_value="UPDATE 1")

    # transaction() context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    return conn


@pytest.fixture
def mock_pool(mock_conn):
    """Mock asyncpg pool whose acquire() yields mock_conn."""
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool


@pytest.fixture
def mock_redis():
    """Mock Redis client with common methods."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.incr = AsyncMock(return_value=1)
    redis.decr = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.ping = AsyncMock(return_value=True)
    redis.eval = AsyncMock(return_value=1)

    pipe = AsyncMock()
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True])
    redis.pipeline = MagicMock(return_value=pipe)

    redis.lpush = AsyncMock(return_value=1)
    redis.ltrim = AsyncMock(return_value=True)

    return redis


def _make_auth_headers(role: str = "MEMBER", user_id: str | None = None):
    """Create a valid JWT token and return (headers_dict, user_id, jti).

    Usage in tests: patch get_current_user or require_role to return the payload,
    or use the returned headers with the client.
    """
    from app.core.security import create_access_token

    if user_id is None:
        user_id = str(uuid.uuid4())

    ttl = timedelta(hours=1)
    token, jti, _ = create_access_token(user_id, role, ttl)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": _TEST_CSRF_TOKEN,
    }
    return headers, user_id, jti


@pytest.fixture
def auth_headers():
    """Factory fixture that returns (headers, user_id, jti) for a given role."""
    return _make_auth_headers


def make_user_dict(
    user_id: str | None = None,
    username: str = "testuser",
    role: str = "MEMBER",
    is_deleted: bool = False,
    is_banned: bool = False,
    ban_reason: str | None = None,
    avatar_url: str | None = None,
):
    """Helper to create a fake user row dict."""
    uid = uuid.UUID(user_id) if user_id else uuid.uuid4()
    now = datetime.now(timezone.utc)
    return {
        "id": uid,
        "username": username,
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$fake$hash",
        "role": role,
        "display_name": username,
        "avatar_url": avatar_url,
        "orcid": None,
        "affiliation": None,
        "bio": None,
        "is_deleted": is_deleted,
        "is_banned": is_banned,
        "ban_reason": ban_reason,
        "created_at": now,
        "updated_at": now,
    }
