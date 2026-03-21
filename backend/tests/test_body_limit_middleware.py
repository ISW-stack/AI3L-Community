"""Tests for body-size limit middleware and validation error handler in app.main.

Covers:
- _get_body_limit helper returns correct limits for known and unknown paths
- RequestValidationError handler returns sanitized 422 responses
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

_TEST_CSRF = "csrf-test-token"


@pytest.fixture
async def bare_client():
    """Minimal test client with CSRF tokens and mocked lifespan deps."""
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
            cookies={"csrf_token": _TEST_CSRF},
            headers={"X-CSRF-Token": _TEST_CSRF},
        ) as ac:
            yield ac


# ---------------------------------------------------------------------------
# _get_body_limit unit tests
# ---------------------------------------------------------------------------


class TestGetBodyLimit:
    """Direct unit tests for the _get_body_limit helper."""

    def test_albums_path_returns_50mb(self):
        from app.main import _get_body_limit

        assert _get_body_limit("/api/v1/albums/") == 50 * 1024 * 1024

    def test_albums_subpath_returns_50mb(self):
        from app.main import _get_body_limit

        assert _get_body_limit("/api/v1/albums/upload") == 50 * 1024 * 1024

    def test_dm_path_returns_50mb(self):
        from app.main import _get_body_limit

        assert _get_body_limit("/api/v1/dm/") == 50 * 1024 * 1024

    def test_dm_subpath_returns_50mb(self):
        from app.main import _get_body_limit

        assert _get_body_limit("/api/v1/dm/send") == 50 * 1024 * 1024

    def test_files_path_returns_20mb(self):
        from app.main import _get_body_limit

        assert _get_body_limit("/api/v1/files/") == 20 * 1024 * 1024

    def test_files_subpath_returns_20mb(self):
        from app.main import _get_body_limit

        assert _get_body_limit("/api/v1/files/upload") == 20 * 1024 * 1024

    def test_unknown_path_returns_default_10mb(self):
        from app.main import MAX_REQUEST_BODY_SIZE, _get_body_limit

        assert _get_body_limit("/api/v1/posts/") == MAX_REQUEST_BODY_SIZE
        assert _get_body_limit("/api/v1/users/me") == MAX_REQUEST_BODY_SIZE
        assert _get_body_limit("/health") == MAX_REQUEST_BODY_SIZE

    def test_default_is_10mb(self):
        from app.main import MAX_REQUEST_BODY_SIZE

        assert MAX_REQUEST_BODY_SIZE == 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# RequestValidationError handler tests
# ---------------------------------------------------------------------------


class TestValidationExceptionHandler:
    """Test that RequestValidationError returns sanitized 422 response."""

    @pytest.mark.anyio
    async def test_invalid_query_param_returns_sanitized_error(self, bare_client: AsyncClient):
        """Send a request with an invalid query param type to trigger validation error.

        GET /api/v1/posts?page=-1 or similar — the exact endpoint doesn't matter,
        we just need to trigger a Pydantic validation error.
        """
        from app.main import RequestValidationError, app, validation_exception_handler

        # Directly invoke the handler to test its output format
        from fastapi import Request as FRequest
        from pydantic import ValidationError

        exc = RequestValidationError(
            errors=[
                {
                    "type": "int_parsing",
                    "loc": ("query", "page"),
                    "msg": "Input should be a valid integer",
                    "input": "abc",
                }
            ]
        )
        # Build a minimal scope for a fake request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        fake_request = FRequest(scope)
        response = await validation_exception_handler(fake_request, exc)

        assert response.status_code == 422
        import json

        body = json.loads(response.body)
        assert body["code"] == "VALIDATION_ERROR"
        assert len(body["errors"]) == 1
        assert body["errors"][0]["field"] == "page"
        assert body["errors"][0]["message"] == "Input should be a valid integer"

    @pytest.mark.anyio
    async def test_multiple_validation_errors_sanitized(self):
        """Multiple errors are all sanitized."""
        from fastapi import Request as FRequest

        from app.main import RequestValidationError, validation_exception_handler

        exc = RequestValidationError(
            errors=[
                {
                    "type": "missing",
                    "loc": ("body", "username"),
                    "msg": "Field required",
                    "input": None,
                },
                {
                    "type": "string_too_short",
                    "loc": ("body", "password"),
                    "msg": "String should have at least 8 characters",
                    "input": "ab",
                },
            ]
        )
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        fake_request = FRequest(scope)
        response = await validation_exception_handler(fake_request, exc)

        assert response.status_code == 422
        import json

        body = json.loads(response.body)
        assert body["code"] == "VALIDATION_ERROR"
        assert len(body["errors"]) == 2
        fields = {e["field"] for e in body["errors"]}
        assert fields == {"username", "password"}

    @pytest.mark.anyio
    async def test_empty_loc_uses_unknown(self):
        """Error with empty loc tuple uses 'unknown' as field name."""
        from fastapi import Request as FRequest

        from app.main import RequestValidationError, validation_exception_handler

        exc = RequestValidationError(
            errors=[
                {
                    "type": "value_error",
                    "loc": (),
                    "msg": "Value error",
                    "input": None,
                }
            ]
        )
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        fake_request = FRequest(scope)
        response = await validation_exception_handler(fake_request, exc)

        import json

        body = json.loads(response.body)
        assert body["errors"][0]["field"] == "unknown"

    @pytest.mark.anyio
    async def test_no_internal_details_leaked(self):
        """Response must not contain 'ctx', 'url', 'type' from Pydantic internals."""
        from fastapi import Request as FRequest

        from app.main import RequestValidationError, validation_exception_handler

        exc = RequestValidationError(
            errors=[
                {
                    "type": "int_parsing",
                    "loc": ("query", "page_size"),
                    "msg": "Input should be a valid integer",
                    "input": "xyz",
                    "ctx": {"error": "some internal detail"},
                    "url": "https://errors.pydantic.dev/...",
                }
            ]
        )
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        fake_request = FRequest(scope)
        response = await validation_exception_handler(fake_request, exc)

        import json

        body = json.loads(response.body)
        # Only "field" and "message" keys should exist in each error
        for error in body["errors"]:
            assert set(error.keys()) == {"field", "message"}
        # No raw pydantic details in the response text
        raw = response.body.decode()
        assert "ctx" not in raw or '"ctx"' not in raw
        assert "pydantic.dev" not in raw
