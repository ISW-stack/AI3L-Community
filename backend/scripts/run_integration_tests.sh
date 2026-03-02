#!/usr/bin/env bash
# =============================================================================
# Run backend integration tests with ephemeral PostgreSQL + Redis containers.
#
# Usage:
#   cd backend
#   bash scripts/run_integration_tests.sh
#
# Prerequisites:
#   - Docker (and docker compose) installed and running
#   - Python venv with requirements-dev.txt installed
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$BACKEND_DIR"

echo "==> Starting test containers..."
docker compose -f docker-compose.test.yml up -d --wait

echo "==> Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
    if docker compose -f docker-compose.test.yml exec -T postgres-test pg_isready -U ai3l_test -d ai3l_test > /dev/null 2>&1; then
        echo "    PostgreSQL is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: PostgreSQL did not become ready in time."
        docker compose -f docker-compose.test.yml down -v
        exit 1
    fi
    sleep 1
done

echo "==> Waiting for Redis to be ready..."
for i in $(seq 1 30); do
    if docker compose -f docker-compose.test.yml exec -T redis-test redis-cli ping > /dev/null 2>&1; then
        echo "    Redis is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Redis did not become ready in time."
        docker compose -f docker-compose.test.yml down -v
        exit 1
    fi
    sleep 1
done

echo "==> Running Alembic migrations against test database..."
export TEST_DATABASE_URL="postgresql://ai3l_test:test_password@localhost:25432/ai3l_test"
export TEST_REDIS_URL="redis://localhost:26379/0"
export POSTGRES_USER=ai3l_test
export POSTGRES_PASSWORD=test_password
export POSTGRES_HOST=localhost
export POSTGRES_PORT=25432
export POSTGRES_DB=ai3l_test
export SECRET_KEY="test-secret-key-at-least-32-characters-long"
export JWT_SECRET_KEY="test-jwt-secret-key"

python -m alembic upgrade head

echo "==> Running integration tests..."
export RUN_INTEGRATION_TESTS=1
python -m pytest tests/integration/ -v --tb=short
TEST_EXIT_CODE=$?

echo "==> Stopping test containers..."
docker compose -f docker-compose.test.yml down -v

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "==> All integration tests passed!"
else
    echo "==> Integration tests FAILED (exit code: $TEST_EXIT_CODE)"
fi

exit $TEST_EXIT_CODE
