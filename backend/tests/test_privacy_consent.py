"""Tests for app.services.privacy_consent — DB consent + Redis guest consent."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest


class TestCreateConsent:
    @patch("app.services.privacy_consent.get_pool")
    async def test_create_consent(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.privacy_consent import create_consent

        mock_get_pool.return_value = mock_pool

        await create_consent(str(uuid.uuid4()), "127.0.0.1")
        mock_conn.execute.assert_called_once()


class TestHasConsent:
    @patch("app.services.privacy_consent.get_pool")
    async def test_has_consent_true(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.privacy_consent import has_consent

        mock_conn.fetchval.return_value = 1
        mock_get_pool.return_value = mock_pool

        result = await has_consent(str(uuid.uuid4()))
        assert result is True

    @patch("app.services.privacy_consent.get_pool")
    async def test_has_consent_false(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.privacy_consent import has_consent

        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        result = await has_consent(str(uuid.uuid4()))
        assert result is False


class TestGuestConsent:
    @patch("app.services.privacy_consent.get_redis")
    async def test_guest_consent_redis_set(self, mock_get_redis):
        from app.services.privacy_consent import create_guest_consent

        redis = AsyncMock()
        mock_get_redis.return_value = redis
        guest_id = str(uuid.uuid4())

        await create_guest_consent(guest_id)
        redis.set.assert_called_once_with(f"consent:guest:{guest_id}", "1", ex=2700)

    @patch("app.services.privacy_consent.get_redis")
    async def test_guest_consent_redis_get_true(self, mock_get_redis):
        from app.services.privacy_consent import has_guest_consent

        redis = AsyncMock()
        redis.exists.return_value = 1
        mock_get_redis.return_value = redis

        result = await has_guest_consent("guest-123")
        assert result is True

    @patch("app.services.privacy_consent.get_redis")
    async def test_guest_consent_redis_get_false(self, mock_get_redis):
        from app.services.privacy_consent import has_guest_consent

        redis = AsyncMock()
        redis.exists.return_value = 0
        mock_get_redis.return_value = redis

        result = await has_guest_consent("guest-123")
        assert result is False
