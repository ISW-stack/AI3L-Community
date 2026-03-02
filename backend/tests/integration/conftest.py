"""Integration test fixtures — real PostgreSQL + Redis.

Skip the entire integration test suite unless RUN_INTEGRATION_TESTS=1 is set.
Fixtures create a real asyncpg pool, run Alembic migrations at session start,
and truncate all tables between tests for isolation.
"""

import os
import subprocess
import sys

import asyncpg
import pytest
import redis.asyncio as aioredis

# ---------------------------------------------------------------------------
# Gate: skip all integration tests unless env var is set
# ---------------------------------------------------------------------------
SKIP_REASON = "Integration tests require RUN_INTEGRATION_TESTS=1"

skip_unless_integration = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason=SKIP_REASON,
)

# ---------------------------------------------------------------------------
# Connection URLs (overridable via environment)
# ---------------------------------------------------------------------------
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://ai3l_test:test_password@localhost:25432/ai3l_test",
)
TEST_REDIS_URL = os.getenv(
    "TEST_REDIS_URL",
    "redis://localhost:26379/0",
)

# Alembic needs a SQLAlchemy-style URL
_SQLALCHEMY_URL = TEST_DB_URL.replace("postgresql://", "postgresql+asyncpg://")


# ---------------------------------------------------------------------------
# Function-scoped: asyncpg pool
# Each test gets its own pool so all async operations share one event loop.
# ---------------------------------------------------------------------------
@pytest.fixture
async def db_pool():
    """Create a real asyncpg pool for the test database."""
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip(SKIP_REASON)

    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=2, max_size=5)
    yield pool
    await pool.close()


# ---------------------------------------------------------------------------
# Function-scoped: Redis client
# ---------------------------------------------------------------------------
@pytest.fixture
async def redis_client():
    """Create a real Redis client for testing."""
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip(SKIP_REASON)

    client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


# ---------------------------------------------------------------------------
# Session-scoped: Run Alembic migrations (upgrade head)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
async def run_migrations():
    """Run Alembic upgrade head via subprocess before all tests.

    Uses subprocess to avoid issues with Alembic's env.py importing app.core.config
    (which reads .env).  We override DATABASE_URL via the environment.
    """
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip(SKIP_REASON)

    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    backend_dir = os.path.abspath(backend_dir)

    env = os.environ.copy()
    # Override the settings that alembic/env.py reads via app.core.config
    env["POSTGRES_USER"] = TEST_DB_URL.split("://")[1].split(":")[0]
    env["POSTGRES_PASSWORD"] = TEST_DB_URL.split(":")[2].split("@")[0]
    env["POSTGRES_HOST"] = TEST_DB_URL.split("@")[1].split(":")[0]
    env["POSTGRES_PORT"] = TEST_DB_URL.split(":")[-1].split("/")[0]
    env["POSTGRES_DB"] = TEST_DB_URL.split("/")[-1]

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Alembic upgrade failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")

    yield

    # Teardown: downgrade to base
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Don't fail the suite on teardown, just warn
        print(
            f"WARNING: Alembic downgrade failed:\nstdout: {result.stdout}\nstderr: {result.stderr}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Per-test: truncate all tables for isolation
# ---------------------------------------------------------------------------
# All known tables in dependency-safe order (children before parents).
_ALL_TABLES = [
    "form_responses",
    "forms",
    "comments",
    "post_history",
    "post_reports",
    "posts",
    "sig_members",
    "sigs",
    "categories",
    "notifications",
    "audit_logs",
    "membership_applications",
    "privacy_consents",
    "invite_codes",
    "users",
]


@pytest.fixture(autouse=True)
async def clean_tables(db_pool):
    """Truncate all tables between tests for isolation."""
    yield
    async with db_pool.acquire() as conn:
        tables = ", ".join(_ALL_TABLES)
        await conn.execute(f"TRUNCATE TABLE {tables} CASCADE")


# ---------------------------------------------------------------------------
# Per-test: flush Redis
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
async def clean_redis(redis_client):
    """Flush Redis between tests for isolation."""
    yield
    await redis_client.flushdb()
