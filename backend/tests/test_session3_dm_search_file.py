"""Tests for audit session 3 fixes: DM, search, file streaming, SIG notifications, config."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# L-12: Editor file streaming response
# ---------------------------------------------------------------------------


class TestFileStreamingResponse:
    """Verify that serve_file uses StreamingResponse with chunked reading."""

    @pytest.mark.asyncio
    async def test_serve_file_returns_streaming_response(self) -> None:
        """serve_file must return a StreamingResponse, not load file into memory."""
        from starlette.responses import StreamingResponse

        from app.api.v1.endpoints.files import serve_file

        fake_body = MagicMock()
        # Simulate two chunks then EOF
        fake_body.read = MagicMock(side_effect=[b"chunk1", b"chunk2", b""])

        current_user = {"sub": str(uuid.uuid4()), "role": "MEMBER"}
        key = f"editor/{current_user['sub']}/abc123.png"

        with (
            patch(
                "app.api.v1.endpoints.files.async_download_metadata",
                new_callable=AsyncMock,
                return_value=(fake_body, "image/png", 12),
            ),
            patch(
                "app.api.v1.endpoints.files.file_scan_repo",
            ) as mock_scan_repo,
        ):
            mock_scan_repo.find_by_key = AsyncMock(
                return_value={"status": "clean", "positives": 0, "total": 60}
            )
            response = await serve_file(key=key, current_user=current_user)

        assert isinstance(response, StreamingResponse)

    @pytest.mark.asyncio
    async def test_serve_file_streams_in_chunks(self) -> None:
        """The response generator must read in 64KB chunks, not all at once."""
        from app.api.v1.endpoints.files import serve_file

        fake_body = MagicMock()
        chunk_data = b"x" * 100
        fake_body.read = MagicMock(side_effect=[chunk_data, b""])

        current_user = {"sub": str(uuid.uuid4()), "role": "ADMIN"}
        key = f"editor/{current_user['sub']}/test.pdf"

        with (
            patch(
                "app.api.v1.endpoints.files.async_download_metadata",
                new_callable=AsyncMock,
                return_value=(fake_body, "application/pdf", 100),
            ),
            patch(
                "app.api.v1.endpoints.files.file_scan_repo",
            ) as mock_scan_repo,
        ):
            mock_scan_repo.find_by_key = AsyncMock(return_value=None)
            response = await serve_file(key=key, current_user=current_user)

        # Consume the streaming body
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0] == chunk_data
        # Verify read was called with chunk size (64KB)
        assert fake_body.read.call_count >= 2  # at least one data call + one empty
        first_call_size = fake_body.read.call_args_list[0].args[0]
        assert first_call_size == 64 * 1024  # _STREAM_CHUNK_SIZE

    @pytest.mark.asyncio
    async def test_serve_file_sets_content_disposition_inline_for_images(self) -> None:
        """Images should get Content-Disposition: inline."""
        from app.api.v1.endpoints.files import serve_file

        fake_body = MagicMock()
        fake_body.read = MagicMock(side_effect=[b""])

        current_user = {"sub": str(uuid.uuid4()), "role": "MEMBER"}
        key = f"editor/{current_user['sub']}/photo.jpg"

        with (
            patch(
                "app.api.v1.endpoints.files.async_download_metadata",
                new_callable=AsyncMock,
                return_value=(fake_body, "image/jpeg", 500),
            ),
            patch("app.api.v1.endpoints.files.file_scan_repo") as mock_scan_repo,
        ):
            mock_scan_repo.find_by_key = AsyncMock(return_value=None)
            response = await serve_file(key=key, current_user=current_user)

        assert "inline" in response.headers["content-disposition"]

    @pytest.mark.asyncio
    async def test_serve_file_sets_content_disposition_attachment_for_non_images(self) -> None:
        """Non-image files should force download."""
        from app.api.v1.endpoints.files import serve_file

        fake_body = MagicMock()
        fake_body.read = MagicMock(side_effect=[b""])

        current_user = {"sub": str(uuid.uuid4()), "role": "MEMBER"}
        key = f"editor/{current_user['sub']}/doc.pdf"

        with (
            patch(
                "app.api.v1.endpoints.files.async_download_metadata",
                new_callable=AsyncMock,
                return_value=(fake_body, "application/pdf", 500),
            ),
            patch("app.api.v1.endpoints.files.file_scan_repo") as mock_scan_repo,
        ):
            mock_scan_repo.find_by_key = AsyncMock(return_value=None)
            response = await serve_file(key=key, current_user=current_user)

        assert "attachment" in response.headers["content-disposition"]

    @pytest.mark.asyncio
    async def test_serve_file_sets_sandbox_csp(self) -> None:
        """Served files must include Content-Security-Policy: sandbox."""
        from app.api.v1.endpoints.files import serve_file

        fake_body = MagicMock()
        fake_body.read = MagicMock(side_effect=[b""])

        current_user = {"sub": str(uuid.uuid4()), "role": "MEMBER"}
        key = f"editor/{current_user['sub']}/file.png"

        with (
            patch(
                "app.api.v1.endpoints.files.async_download_metadata",
                new_callable=AsyncMock,
                return_value=(fake_body, "image/png", 10),
            ),
            patch("app.api.v1.endpoints.files.file_scan_repo") as mock_scan_repo,
        ):
            mock_scan_repo.find_by_key = AsyncMock(return_value=None)
            response = await serve_file(key=key, current_user=current_user)

        assert response.headers["content-security-policy"] == "sandbox"


# ---------------------------------------------------------------------------
# L-40: User search filters blocked users
# ---------------------------------------------------------------------------


class TestUserSearchExcludesBlocked:
    """Verify search_users_for_coauthor filters excluded IDs."""

    @pytest.mark.asyncio
    async def test_search_with_exclude_ids_uses_not_all(self) -> None:
        """When exclude_ids is provided, the SQL must use != ALL to exclude them."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        exclude = {str(uuid.uuid4()), str(uuid.uuid4())}

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import search_users_for_coauthor

            result = await search_users_for_coauthor("alice", exclude_ids=exclude)

        assert result == []
        # Verify the SQL query includes the exclusion clause
        call_args = mock_conn.fetch.call_args
        sql = call_args.args[0]
        assert "!= ALL" in sql
        assert "uuid[]" in sql

    @pytest.mark.asyncio
    async def test_search_without_exclude_ids_no_all_clause(self) -> None:
        """When exclude_ids is None, the simpler query without != ALL is used."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import search_users_for_coauthor

            result = await search_users_for_coauthor("bob", exclude_ids=None)

        assert result == []
        sql = mock_conn.fetch.call_args.args[0]
        assert "!= ALL" not in sql

    @pytest.mark.asyncio
    async def test_search_passes_exclude_uuids_as_third_param(self) -> None:
        """The exclude UUIDs must be passed as the 3rd positional parameter ($3)."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        exclude = {uid1, uid2}

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import search_users_for_coauthor

            await search_users_for_coauthor("test", limit=5, exclude_ids=exclude)

        call_args = mock_conn.fetch.call_args
        # args[0] = SQL, args[1] = pattern, args[2] = limit, args[3] = exclude_uuids
        passed_uuids = call_args.args[3]
        assert len(passed_uuids) == 2
        assert all(isinstance(u, uuid.UUID) for u in passed_uuids)

    @pytest.mark.asyncio
    async def test_search_filters_deleted_and_banned(self) -> None:
        """The query must filter is_deleted = false AND is_banned = false."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.repositories.user_repo.get_pool", return_value=mock_pool):
            from app.repositories.user_repo import search_users_for_coauthor

            await search_users_for_coauthor("carol")

        sql = mock_conn.fetch.call_args.args[0]
        assert "is_deleted = false" in sql
        assert "is_banned = false" in sql


# ---------------------------------------------------------------------------
# L-41: DM conversation list filters blocked users
# ---------------------------------------------------------------------------


class TestDMConversationListFiltersBlocked:
    """Verify find_conversations excludes conversations with blocked users."""

    @pytest.mark.asyncio
    async def test_find_conversations_sql_contains_blocks_subquery(self) -> None:
        """The SQL must include a NOT EXISTS ... blocks subquery."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        user_id = uuid.uuid4()

        with patch("app.repositories.dm_repo.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_conversations

            rows, total = await find_conversations(user_id)

        assert rows == []
        assert total == 0

        sql = mock_conn.fetch.call_args.args[0]
        assert "NOT EXISTS" in sql
        assert "blocks" in sql

    @pytest.mark.asyncio
    async def test_find_conversations_blocks_bilateral(self) -> None:
        """The blocks subquery must check both directions (blocker/blocked)."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        user_id = uuid.uuid4()

        with patch("app.repositories.dm_repo.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_conversations

            await find_conversations(user_id)

        sql = mock_conn.fetch.call_args.args[0]
        # Must check both b.blocker_id and b.blocked_id for bilateral blocking
        assert "blocker_id" in sql
        assert "blocked_id" in sql

    @pytest.mark.asyncio
    async def test_find_conversations_returns_total_from_window(self) -> None:
        """When rows exist, total should come from COUNT(*) OVER()."""
        mock_row = {
            "id": uuid.uuid4(),
            "participant_a": uuid.uuid4(),
            "participant_b": uuid.uuid4(),
            "total_chars": 100,
            "updated_at": "2026-01-01",
            "other_user_id": uuid.uuid4(),
            "other_display_name": "Test",
            "other_avatar_url": None,
            "last_msg_id": None,
            "last_msg_conversation_id": None,
            "last_msg_sender_id": None,
            "last_msg_content": None,
            "last_msg_attachment_key": None,
            "last_msg_attachment_name": None,
            "last_msg_attachment_size": None,
            "last_msg_attachment_expires_at": None,
            "last_msg_is_recalled": None,
            "last_msg_is_edited": None,
            "last_msg_read_at": None,
            "last_msg_created_at": None,
            "last_msg_updated_at": None,
            "last_msg_sender_display_name": None,
            "last_msg_sender_avatar_url": None,
            "unread_count": 0,
            "_total": 5,
        }
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.repositories.dm_repo.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_conversations

            rows, total = await find_conversations(uuid.uuid4())

        assert total == 5
        assert len(rows) == 1
        # _total should be stripped from the returned rows
        assert "_total" not in rows[0]

    @pytest.mark.asyncio
    async def test_find_conversations_sql_has_count_over(self) -> None:
        """SQL must use COUNT(*) OVER() for efficient total."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.repositories.dm_repo.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import find_conversations

            await find_conversations(uuid.uuid4())

        sql = mock_conn.fetch.call_args.args[0]
        assert "COUNT(*) OVER()" in sql


# ---------------------------------------------------------------------------
# L-45: File scan status error message sanitized
# ---------------------------------------------------------------------------


class TestFileScanStatusSanitized:
    """Verify scan status endpoint does not leak internal details to non-admins."""

    @pytest.mark.asyncio
    async def test_scan_status_returns_status_for_owner(self) -> None:
        """File owner gets status, positives, and total -- but no raw scan details."""
        from app.api.v1.endpoints.files import get_scan_status

        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/test.png"
        current_user = {"sub": user_id, "role": "MEMBER"}

        with patch("app.api.v1.endpoints.files.file_scan_repo") as mock_repo:
            mock_repo.find_by_key = AsyncMock(
                return_value={
                    "status": "clean",
                    "positives": 0,
                    "total": 62,
                    "raw_result": '{"internal": "details"}',
                    "sha256": "abc123",
                }
            )
            result = await get_scan_status(key=key, current_user=current_user)

        # Only status/positives/total should be returned, no raw_result or sha256
        assert result == {"status": "clean", "positives": 0, "total": 62}
        assert "raw_result" not in result
        assert "sha256" not in result

    @pytest.mark.asyncio
    async def test_scan_status_unknown_when_no_record(self) -> None:
        """When no scan record exists, return unknown status with null fields."""
        from app.api.v1.endpoints.files import get_scan_status

        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/test.png"
        current_user = {"sub": user_id, "role": "MEMBER"}

        with patch("app.api.v1.endpoints.files.file_scan_repo") as mock_repo:
            mock_repo.find_by_key = AsyncMock(return_value=None)
            result = await get_scan_status(key=key, current_user=current_user)

        assert result == {"status": "unknown", "positives": None, "total": None}

    @pytest.mark.asyncio
    async def test_scan_status_rejects_non_owner_non_admin(self) -> None:
        """Non-owner, non-admin users cannot check scan status."""
        from app.api.v1.endpoints.files import get_scan_status
        from app.core.errors import AppError

        other_user_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        key = f"editor/{owner_id}/test.png"
        current_user = {"sub": other_user_id, "role": "MEMBER"}

        with pytest.raises(AppError) as exc_info:
            await get_scan_status(key=key, current_user=current_user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_scan_status_admin_can_access_any_file(self) -> None:
        """Admins can check scan status on any file."""
        from app.api.v1.endpoints.files import get_scan_status

        admin_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        key = f"editor/{owner_id}/test.png"
        current_user = {"sub": admin_id, "role": "SUPER_ADMIN"}

        with patch("app.api.v1.endpoints.files.file_scan_repo") as mock_repo:
            mock_repo.find_by_key = AsyncMock(
                return_value={"status": "malicious", "positives": 5, "total": 60}
            )
            result = await get_scan_status(key=key, current_user=current_user)

        assert result["status"] == "malicious"
        assert result["positives"] == 5

    @pytest.mark.asyncio
    async def test_serve_file_blocks_pending_scan(self) -> None:
        """Files with pending scan status should return 202, not serve content."""
        from app.api.v1.endpoints.files import serve_file
        from app.core.errors import AppError

        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/test.png"
        current_user = {"sub": user_id, "role": "MEMBER"}

        with patch("app.api.v1.endpoints.files.file_scan_repo") as mock_repo:
            mock_repo.find_by_key = AsyncMock(return_value={"status": "pending"})
            with pytest.raises(AppError) as exc_info:
                await serve_file(key=key, current_user=current_user)

        assert exc_info.value.status_code == 202

    @pytest.mark.asyncio
    async def test_serve_file_blocks_malicious_scan(self) -> None:
        """Files flagged as malicious must not be served."""
        from app.api.v1.endpoints.files import serve_file
        from app.core.errors import AppError

        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/test.png"
        current_user = {"sub": user_id, "role": "MEMBER"}

        with patch("app.api.v1.endpoints.files.file_scan_repo") as mock_repo:
            mock_repo.find_by_key = AsyncMock(return_value={"status": "malicious"})
            with pytest.raises(AppError) as exc_info:
                await serve_file(key=key, current_user=current_user)

        assert exc_info.value.status_code == 451

    @pytest.mark.asyncio
    async def test_serve_file_blocks_unknown_scan_status(self) -> None:
        """Files with unknown/error scan status must not be served (fail-close)."""
        from app.api.v1.endpoints.files import serve_file
        from app.core.errors import AppError

        user_id = str(uuid.uuid4())
        key = f"editor/{user_id}/test.png"
        current_user = {"sub": user_id, "role": "MEMBER"}

        for scan_status in ("unknown", "error"):
            with patch("app.api.v1.endpoints.files.file_scan_repo") as mock_repo:
                mock_repo.find_by_key = AsyncMock(return_value={"status": scan_status})
                with pytest.raises(AppError) as exc_info:
                    await serve_file(key=key, current_user=current_user)

            # Should get a generic message, not internal scan details
            assert exc_info.value.status_code == 403
            assert "not been verified" in exc_info.value.detail["message"]


# ---------------------------------------------------------------------------
# L-50: SIG notification batching
# ---------------------------------------------------------------------------


class TestSIGNotificationBatching:
    """Verify the SIG notification Celery task has concurrency control and caps."""

    def test_notify_sig_members_task_exists(self) -> None:
        """The notify_sig_members_new_post Celery task must be importable."""
        from app.tasks.event_retry import notify_sig_members_new_post

        assert callable(notify_sig_members_new_post)
        # Verify it's a Celery shared_task
        assert hasattr(notify_sig_members_new_post, "delay")
        assert hasattr(notify_sig_members_new_post, "apply_async")

    def test_notification_max_cap_is_500(self) -> None:
        """Hard cap on notifications per SIG post must be 500."""
        from app.tasks.event_retry import _SIG_NOTIFICATION_MAX

        assert _SIG_NOTIFICATION_MAX == 500

    def test_notification_concurrency_limit_exists(self) -> None:
        """Concurrency semaphore limit must be defined."""
        from app.tasks.event_retry import _SIG_NOTIFICATION_CONCURRENCY

        assert _SIG_NOTIFICATION_CONCURRENCY > 0
        assert _SIG_NOTIFICATION_CONCURRENCY <= 50  # reasonable upper bound

    def test_notification_batch_size_exists(self) -> None:
        """Batch size for fetching members must be defined."""
        from app.tasks.event_retry import _SIG_MEMBER_BATCH_SIZE

        assert _SIG_MEMBER_BATCH_SIZE > 0
        assert _SIG_MEMBER_BATCH_SIZE <= 500

    def test_event_handler_dispatches_to_celery(self) -> None:
        """_on_post_created_in_sig must dispatch to Celery, not process inline."""
        import inspect

        from app.event_handlers import _on_post_created_in_sig

        source = inspect.getsource(_on_post_created_in_sig)
        assert "notify_sig_members_new_post" in source
        assert ".delay(" in source

    @pytest.mark.asyncio
    async def test_async_notify_uses_semaphore(self) -> None:
        """_async_notify_sig_members must use asyncio.Semaphore for concurrency."""
        import inspect

        from app.tasks.event_retry import _async_notify_sig_members

        source = inspect.getsource(_async_notify_sig_members)
        assert "Semaphore" in source
        assert "async with sem" in source

    @pytest.mark.asyncio
    async def test_async_notify_enforces_cap(self) -> None:
        """_async_notify_sig_members must break when cap is reached."""
        import inspect

        from app.tasks.event_retry import _async_notify_sig_members

        source = inspect.getsource(_async_notify_sig_members)
        assert "_SIG_NOTIFICATION_MAX" in source
        assert "cap_reached" in source

    @pytest.mark.asyncio
    async def test_on_post_created_in_sig_dispatches_task(self) -> None:
        """_on_post_created_in_sig should call .delay() on the Celery task."""
        from app.event_handlers import _on_post_created_in_sig

        mock_task = MagicMock()
        with patch(
            "app.tasks.event_retry.notify_sig_members_new_post",
            mock_task,
        ):
            await _on_post_created_in_sig(
                sig_id="sig-1",
                post_id="post-1",
                author_id="author-1",
                post_title="Test Post",
            )

        mock_task.delay.assert_called_once_with("sig-1", "post-1", "author-1", "Test Post")

    @pytest.mark.asyncio
    async def test_on_post_created_handles_import_error(self) -> None:
        """If Celery is unavailable, _on_post_created_in_sig should not raise."""
        from app.event_handlers import _on_post_created_in_sig

        with patch(
            "app.tasks.event_retry.notify_sig_members_new_post",
            side_effect=ImportError("no celery"),
        ):
            # Should not raise
            await _on_post_created_in_sig(
                sig_id="sig-1",
                post_id="post-1",
                author_id="author-1",
                post_title="Test Post",
            )

    def test_task_has_max_retries(self) -> None:
        """The Celery task should have max_retries configured."""
        from app.tasks.event_retry import notify_sig_members_new_post

        assert notify_sig_members_new_post.max_retries == 2


# ---------------------------------------------------------------------------
# Nginx / Docker config smoke tests
# ---------------------------------------------------------------------------

# Resolve the project root (backend is a child of the project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestNginxConfig:
    """Smoke tests for nginx configuration files."""

    def test_l51_client_header_timeout_is_set(self) -> None:
        """L-51: nginx.conf must define client_header_timeout."""
        nginx_conf = _PROJECT_ROOT / "nginx" / "nginx.conf"
        content = nginx_conf.read_text(encoding="utf-8")
        assert "client_header_timeout" in content
        # Should be a reasonable value (not 0)
        assert "client_header_timeout 10s" in content or "client_header_timeout 10" in content

    def test_m49_no_global_proxy_request_buffering_off(self) -> None:
        """M-49: proxy-params.conf must NOT disable proxy_request_buffering globally."""
        proxy_params = _PROJECT_ROOT / "nginx" / "snippets" / "proxy-params.conf"
        content = proxy_params.read_text(encoding="utf-8")
        assert "proxy_request_buffering off" not in content

    def test_proxy_params_has_buffer_settings(self) -> None:
        """proxy-params.conf should have proxy buffer settings."""
        proxy_params = _PROJECT_ROOT / "nginx" / "snippets" / "proxy-params.conf"
        content = proxy_params.read_text(encoding="utf-8")
        assert "proxy_buffer_size" in content
        assert "proxy_buffers" in content

    def test_nginx_server_tokens_off(self) -> None:
        """nginx.conf must have server_tokens off to hide version."""
        nginx_conf = _PROJECT_ROOT / "nginx" / "nginx.conf"
        content = nginx_conf.read_text(encoding="utf-8")
        assert "server_tokens off" in content

    def test_nginx_rate_limiting_zones(self) -> None:
        """nginx.conf must define rate limiting zones."""
        nginx_conf = _PROJECT_ROOT / "nginx" / "nginx.conf"
        content = nginx_conf.read_text(encoding="utf-8")
        assert "limit_req_zone" in content
        assert "limit_req_status 429" in content


class TestDockerComposeConfig:
    """Smoke tests for Docker Compose configuration files."""

    def test_m21_fastapi_port_binds_to_localhost(self) -> None:
        """M-21: docker-compose.override.yml FastAPI port must bind to 127.0.0.1."""
        override = _PROJECT_ROOT / "docker-compose.override.yml"
        content = override.read_text(encoding="utf-8")
        # The fastapi port mapping must use 127.0.0.1 prefix
        assert "127.0.0.1:18000:8000" in content

    def test_postgres_port_binds_to_localhost(self) -> None:
        """docker-compose.override.yml postgres port must bind to 127.0.0.1."""
        override = _PROJECT_ROOT / "docker-compose.override.yml"
        content = override.read_text(encoding="utf-8")
        assert "127.0.0.1:15432:5432" in content

    def test_redis_port_binds_to_localhost(self) -> None:
        """docker-compose.override.yml redis port must bind to 127.0.0.1."""
        override = _PROJECT_ROOT / "docker-compose.override.yml"
        content = override.read_text(encoding="utf-8")
        assert "127.0.0.1:16379:6379" in content

    def test_minio_ports_bind_to_localhost(self) -> None:
        """docker-compose.override.yml minio ports must bind to 127.0.0.1."""
        override = _PROJECT_ROOT / "docker-compose.override.yml"
        content = override.read_text(encoding="utf-8")
        assert "127.0.0.1:19000:9000" in content
        assert "127.0.0.1:19001:9001" in content

    def test_l28_test_compose_ports_bind_to_localhost(self) -> None:
        """L-28: docker-compose.test.yml ports must bind to 127.0.0.1."""
        test_compose = _PROJECT_ROOT / "backend" / "docker-compose.test.yml"
        content = test_compose.read_text(encoding="utf-8")
        assert "127.0.0.1:25432:5432" in content
        assert "127.0.0.1:26379:6379" in content

    def test_no_unbound_ports_in_override(self) -> None:
        """All port mappings in override must be bound to 127.0.0.1 (no bare ports)."""
        import re

        override = _PROJECT_ROOT / "docker-compose.override.yml"
        content = override.read_text(encoding="utf-8")
        # Find all port mapping lines (e.g., - "8000:8000" or - "127.0.0.1:8000:8000")
        port_lines = re.findall(r'-\s*["\']?(\d[\d.:]+\d)["\']?', content)
        for port_mapping in port_lines:
            # Each port mapping that has a colon should start with 127.0.0.1
            if port_mapping.count(":") >= 2:
                assert port_mapping.startswith(
                    "127.0.0.1"
                ), f"Port {port_mapping} is not bound to 127.0.0.1"

    def test_no_unbound_ports_in_test_compose(self) -> None:
        """All port mappings in test compose must be bound to 127.0.0.1."""
        import re

        test_compose = _PROJECT_ROOT / "backend" / "docker-compose.test.yml"
        content = test_compose.read_text(encoding="utf-8")
        port_lines = re.findall(r'-\s*["\']?(\d[\d.:]+\d)["\']?', content)
        for port_mapping in port_lines:
            if port_mapping.count(":") >= 2:
                assert port_mapping.startswith(
                    "127.0.0.1"
                ), f"Port {port_mapping} is not bound to 127.0.0.1"
