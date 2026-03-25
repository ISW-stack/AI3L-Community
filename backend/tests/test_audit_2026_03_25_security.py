"""Tests for security audit fixes (2026-03-25).

Covers:
  H-03: post_owner_id fetched inside transaction (comment service)
  H-04: Consolidated file path error messages (files endpoint)
  M-04: WS session revalidation interval = 60s
  M-05: Invite code revocation ownership check
  L-02: Health endpoint returns "unavailable" not "connection failed"
  L-03: IP ban check logs warning on failure
  L-14: Avatar proxy streaming size limit
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# H-03: post_owner_id derived from transaction-consistent data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_h03_comment_create_uses_transaction_post_owner_id(mock_pool, mock_conn, mock_redis):
    """create_comment must derive post_owner_id from the transactional post row,
    not from a separate pre-transaction query."""
    from app.services.comment import create_comment

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    # The real owner from the transaction should be this:
    real_owner_id = uuid.uuid4()

    # Pre-check owner (may be stale -- this simulates the race scenario)
    stale_owner_id = str(uuid.uuid4())

    # The post row returned inside the transaction
    post_row = {
        "user_id": real_owner_id,
        "allow_comments": True,
        "comment_count": 0,
        "type": "discussion",
    }

    # Comment row returned by insert
    comment_row = {
        "id": uuid.uuid4(),
        "post_id": post_id,
        "user_id": uuid.UUID(user_id),
        "parent_id": None,
        "content": "hello",
        "mentions": None,
        "reactions": {},
        "is_deleted": False,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }

    mock_emit = AsyncMock()
    mock_row_to_comment = AsyncMock(
        return_value={
            "id": str(comment_row["id"]),
            "author": {"display_name": "Test", "username": "test"},
        }
    )

    with (
        patch("app.services.comment.get_pool", return_value=mock_pool),
        patch("app.services.comment.get_redis", return_value=mock_redis),
        patch(
            "app.repositories.post_repo.find_owner_id",
            new_callable=AsyncMock,
            return_value=stale_owner_id,
        ),
        patch(
            "app.repositories.comment_repo.find_post_for_comment",
            new_callable=AsyncMock,
            return_value=post_row,
        ),
        patch(
            "app.repositories.comment_repo.insert",
            new_callable=AsyncMock,
            return_value=comment_row,
        ),
        patch(
            "app.services.comment.async_row_to_comment",
            mock_row_to_comment,
        ),
        patch("app.services.comment.emit", mock_emit),
        patch(
            "app.core.blacklist.get_blocked_user_ids",
            new_callable=AsyncMock,
            return_value=set(),
        ),
    ):
        await create_comment(post_id, user_id, "hello")

        # Verify emit was called with the TRANSACTION-derived owner, not the stale one
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["post_owner_id"] == str(real_owner_id), (
            f"Expected post_owner_id={real_owner_id} from transaction, "
            f"got {call_kwargs['post_owner_id']}"
        )
        # Must NOT be the stale owner
        assert call_kwargs["post_owner_id"] != stale_owner_id


@pytest.mark.asyncio
async def test_h03_post_owner_id_not_fetched_outside_transaction():
    """Verify that the emit call uses post_owner_id set inside the transaction block,
    not the pre_check_owner_id."""
    import inspect

    from app.services import comment

    source = inspect.getsource(comment.create_comment)
    # The variable used for emit should be post_owner_id derived inside the transaction
    assert "post_owner_id = str(post[" in source, (
        "post_owner_id should be derived from the transaction post row"
    )
    # The pre-check variable should be renamed
    assert "pre_check_owner_id" in source, (
        "The pre-transaction owner lookup should be named pre_check_owner_id"
    )


# ---------------------------------------------------------------------------
# H-04: Consolidated file path error messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch(
    "app.core.deps.get_user_by_id",
    new_callable=AsyncMock,
    return_value={"is_banned": False, "is_deleted": False},
)
@patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
async def test_h04_delete_file_all_invalid_keys_same_error(
    _mock_session, _mock_user_check, client, auth_headers
):
    """All invalid key patterns should return the same generic error message."""
    headers, user_id, _ = auth_headers("MEMBER")
    # Various invalid key patterns that should all yield the same error
    invalid_keys = [
        "editor/../etc/passwd",       # path traversal
        "editor/abc/<script>",         # unsafe chars
        "not-editor/user-id/file.png", # not starting with editor/
        "avatars/user-id/file.png",    # not an editor file
        "some/random/path",            # not editor prefix
    ]

    for key in invalid_keys:
        resp = await client.delete(f"/api/v1/files/content/{key}", headers=headers)
        assert resp.status_code == 400, f"Key '{key}' should return 400, got {resp.status_code}"
        data = resp.json()
        detail = data.get("detail")
        # detail may be dict (AppError) or string
        msg = detail.get("message", "") if isinstance(detail, dict) else str(detail)
        assert "invalid file key" in msg.lower(), (
            f"Key '{key}' should return 'Invalid file key.', got '{msg}'"
        )


@pytest.mark.asyncio
@patch(
    "app.core.deps.get_user_by_id",
    new_callable=AsyncMock,
    return_value={"is_banned": False, "is_deleted": False},
)
@patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
async def test_h04_valid_editor_key_passes_validation(
    _mock_session, _mock_user_check, client, auth_headers
):
    """A valid editor key should pass the consolidated validation gate."""
    headers, user_id, _ = auth_headers("MEMBER")
    key = f"editor/{user_id}/abc123.png"

    with (
        patch(
            "app.api.v1.endpoints.files.async_get_file_size",
            new_callable=AsyncMock,
            return_value=1024,
        ),
        patch("app.api.v1.endpoints.files.async_delete_file", new_callable=AsyncMock),
        patch(
            "app.api.v1.endpoints.files.user_repo.increment_storage_used",
            new_callable=AsyncMock,
        ),
        patch(
            "app.api.v1.endpoints.files.file_scan_repo.delete_by_key",
            new_callable=AsyncMock,
        ),
    ):
        resp = await client.delete(f"/api/v1/files/content/{key}", headers=headers)
        # Should NOT get 400 "Invalid file key." -- it passes validation
        if resp.status_code == 400:
            data = resp.json()
            detail = data.get("detail")
            msg = detail.get("message", "") if isinstance(detail, dict) else str(detail)
            assert "invalid file key" not in msg.lower()


# ---------------------------------------------------------------------------
# M-04: WS session revalidation interval
# ---------------------------------------------------------------------------


def test_m04_ws_session_revalidation_interval_is_60():
    """WS_SESSION_REVALIDATION_INTERVAL must be 60 seconds (not 300)."""
    from app.api.v1.endpoints.ws import WS_SESSION_REVALIDATION_INTERVAL

    assert WS_SESSION_REVALIDATION_INTERVAL == 60, (
        f"Expected 60, got {WS_SESSION_REVALIDATION_INTERVAL}"
    )


# ---------------------------------------------------------------------------
# M-05: Invite code revocation ownership check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch(
    "app.core.deps.get_user_by_id",
    new_callable=AsyncMock,
    return_value={"is_banned": False, "is_deleted": False},
)
@patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
async def test_m05_admin_cannot_revoke_other_admins_invite_code(
    _mock_session, _mock_user_check, client, auth_headers
):
    """An ADMIN should not be able to revoke an invite code created by another ADMIN."""
    headers, admin_id, _ = auth_headers("ADMIN")
    other_admin_id = str(uuid.uuid4())
    code_id = uuid.uuid4()

    code_info = {"id": code_id, "created_by": uuid.UUID(other_admin_id)}

    with (
        patch(
            "app.repositories.invite_code_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=code_info,
        ),
        patch(
            "app.repositories.invite_code_repo.revoke",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_revoke,
    ):
        resp = await client.patch(
            f"/api/v1/admin/invite-codes/{code_id}/revoke", headers=headers
        )
        assert resp.status_code == 403
        data = resp.json()
        detail = data.get("detail")
        msg = detail.get("message", "") if isinstance(detail, dict) else str(detail)
        assert "only revoke your own" in msg.lower()
        mock_revoke.assert_not_called()


@pytest.mark.asyncio
@patch(
    "app.core.deps.get_user_by_id",
    new_callable=AsyncMock,
    return_value={"is_banned": False, "is_deleted": False},
)
@patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
async def test_m05_admin_can_revoke_own_invite_code(
    _mock_session, _mock_user_check, client, auth_headers
):
    """An ADMIN should be able to revoke their own invite code."""
    headers, admin_id, _ = auth_headers("ADMIN")
    code_id = uuid.uuid4()

    code_info = {"id": code_id, "created_by": uuid.UUID(admin_id)}

    with (
        patch(
            "app.repositories.invite_code_repo.find_by_id",
            new_callable=AsyncMock,
            return_value=code_info,
        ),
        patch(
            "app.repositories.invite_code_repo.revoke",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("app.core.event_bus.emit", new_callable=AsyncMock),
    ):
        resp = await client.patch(
            f"/api/v1/admin/invite-codes/{code_id}/revoke", headers=headers
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
@patch(
    "app.core.deps.get_user_by_id",
    new_callable=AsyncMock,
    return_value={"is_banned": False, "is_deleted": False},
)
@patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
async def test_m05_super_admin_can_revoke_any_invite_code(
    _mock_session, _mock_user_check, client, auth_headers
):
    """SUPER_ADMIN should be able to revoke any invite code regardless of creator."""
    headers, super_admin_id, _ = auth_headers("SUPER_ADMIN")
    code_id = uuid.uuid4()

    with (
        patch(
            "app.repositories.invite_code_repo.find_by_id",
            new_callable=AsyncMock,
        ) as mock_find,
        patch(
            "app.repositories.invite_code_repo.revoke",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("app.core.event_bus.emit", new_callable=AsyncMock),
    ):
        resp = await client.patch(
            f"/api/v1/admin/invite-codes/{code_id}/revoke", headers=headers
        )
        assert resp.status_code == 200
        # SUPER_ADMIN should NOT need to look up the code for ownership
        mock_find.assert_not_called()


# ---------------------------------------------------------------------------
# L-02: Health endpoint returns "unavailable" not "connection failed"
# ---------------------------------------------------------------------------


def test_l02_health_error_messages_say_unavailable():
    """Health endpoint error strings must use 'unavailable', not 'connection failed'."""
    import inspect

    from app.api.v1.endpoints import health

    source = inspect.getsource(health)
    assert "connection failed" not in source, (
        "Health endpoint should not contain 'connection failed' -- use 'unavailable'"
    )
    assert 'error="unavailable"' in source


@pytest.mark.asyncio
@patch(
    "app.core.deps.get_user_by_id",
    new_callable=AsyncMock,
    return_value={"is_banned": False, "is_deleted": False},
)
@patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True)
async def test_l02_health_pg_failure_returns_unavailable(
    _mock_session, _mock_user_check, client, auth_headers
):
    """When PostgreSQL is down, the error field should say 'unavailable'."""
    headers, _, _ = auth_headers("SUPER_ADMIN")

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(side_effect=Exception("pg down"))
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(side_effect=Exception("redis down"))

    with (
        patch("app.api.v1.endpoints.health.get_pool", return_value=mock_pool),
        patch("app.api.v1.endpoints.health.get_redis", return_value=mock_redis),
        patch("app.core.storage.get_storage", side_effect=Exception("storage down")),
    ):
        resp = await client.get("/api/v1/health", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for dep in data["dependencies"]:
            if dep["status"] == "unhealthy":
                assert dep["error"] == "unavailable", (
                    f"Dependency {dep['name']} error should be 'unavailable', "
                    f"got '{dep['error']}'"
                )


# ---------------------------------------------------------------------------
# L-03: IP ban check logs warning on failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l03_ip_ban_check_logs_warning_on_failure():
    """When IP ban check fails, a warning must be logged (not silently swallowed)."""
    import inspect

    from app import main

    source = inspect.getsource(main.check_ip_ban)
    # Must contain logging call
    assert "logger.warning" in source, "IP ban check_ip_ban must log a warning on failure"
    assert "IP ban check failed" in source, (
        "Warning message should mention 'IP ban check failed'"
    )
    assert "exc_info=True" in source, "Warning should include exc_info=True for debugging"


@pytest.mark.asyncio
async def test_l03_ip_ban_allows_request_on_failure(client):
    """When the IP ban check fails, the request should still be allowed through."""
    with (
        patch(
            "app.services.ip_ban.is_ip_banned",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Redis connection refused"),
        ),
    ):
        # Any GET endpoint that doesn't require auth should work
        resp = await client.get("/api/v1/health/live")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# L-14: Avatar proxy streaming size limit
# ---------------------------------------------------------------------------


def test_l14_avatar_proxy_uses_streaming():
    """The avatar proxy must use stream=True and iter_content for size limiting."""
    import inspect

    from app.api.v1.endpoints import about

    source = inspect.getsource(about.get_contributor_avatar)
    assert "stream=True" in source, "Avatar proxy must use stream=True"
    assert "iter_content" in source, "Avatar proxy must use iter_content for streaming"


# ---------------------------------------------------------------------------
# M-05 (supplemental): invite_code_repo.find_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m05_invite_code_repo_find_by_id_returns_dict(mock_pool, mock_conn):
    """find_by_id should return a dict when the code exists."""
    from app.repositories import invite_code_repo

    code_id = uuid.uuid4()
    row_data = {
        "id": code_id,
        "code": "ABC123",
        "created_by": uuid.uuid4(),
        "consumed_by": None,
        "consumed_at": None,
        "expires_at": None,
        "created_at": "2026-01-01",
    }

    mock_conn.fetchrow = AsyncMock(return_value=row_data)

    with patch("app.repositories.invite_code_repo.get_pool", return_value=mock_pool):
        result = await invite_code_repo.find_by_id(code_id)
        assert result is not None
        assert result["id"] == code_id


@pytest.mark.asyncio
async def test_m05_invite_code_repo_find_by_id_returns_none(mock_pool, mock_conn):
    """find_by_id should return None when the code does not exist."""
    from app.repositories import invite_code_repo

    code_id = uuid.uuid4()
    mock_conn.fetchrow = AsyncMock(return_value=None)

    with patch("app.repositories.invite_code_repo.get_pool", return_value=mock_pool):
        result = await invite_code_repo.find_by_id(code_id)
        assert result is None
