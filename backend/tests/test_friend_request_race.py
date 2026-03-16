"""Tests for friend request race condition fix (C3).

Verifies that send_friend_request:
- Uses FOR UPDATE to prevent concurrent mutual requests from creating duplicates
- Auto-accepts when a pending request from the other user already exists
- Returns 409 conflict when a duplicate request is sent
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import AppError


class TestAutoAcceptMutualRequest:
    """When user B sends a request and user A already has a pending request to B,
    the system should auto-accept within a single transaction."""

    @pytest.mark.anyio
    async def test_auto_accept_when_mutual_pending_request_exists(
        self, mock_pool, mock_conn,
    ) -> None:
        from app.services.social import send_friend_request

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        friendship_id = uuid.uuid4()

        # Existing pending request: A → B
        existing = {
            "id": friendship_id,
            "requester_id": user_a,
            "addressee_id": user_b,
            "status": "PENDING",
        }
        accepted = {**existing, "status": "ACCEPTED"}

        with (
            patch("app.services.social.social_repo") as mock_repo,
            patch("app.services.social.emit", new_callable=AsyncMock),
        ):
            mock_repo.is_blocked = AsyncMock(return_value=False)
            mock_repo.find_friendship_between = AsyncMock(return_value=existing)
            mock_repo.accept_friendship = AsyncMock(return_value=accepted)
            mock_repo.is_following = AsyncMock(return_value=False)
            mock_repo.insert_follow = AsyncMock()

            # User B sends request to A → should auto-accept
            result = await send_friend_request(mock_pool, user_b, user_a)

        assert result["status"] == "ACCEPTED"
        # Verify FOR UPDATE was used
        mock_repo.find_friendship_between.assert_awaited_once_with(
            mock_conn, user_b, user_a, for_update=True
        )
        mock_repo.accept_friendship.assert_awaited_once_with(mock_conn, friendship_id)


class TestDuplicateRequestConflict:
    """Sending a friend request when one is already pending should raise 409."""

    @pytest.mark.anyio
    async def test_duplicate_pending_request_returns_conflict(
        self, mock_pool, mock_conn,
    ) -> None:
        from app.services.social import send_friend_request

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        # Existing pending request: A → B
        existing = {
            "id": uuid.uuid4(),
            "requester_id": user_a,
            "addressee_id": user_b,
            "status": "PENDING",
        }

        with patch("app.services.social.social_repo") as mock_repo:
            mock_repo.is_blocked = AsyncMock(return_value=False)
            mock_repo.find_friendship_between = AsyncMock(return_value=existing)

            with pytest.raises(AppError) as exc_info:
                # A sends again → duplicate, should be 409
                await send_friend_request(mock_pool, user_a, user_b)

            assert exc_info.value.status_code == 409
