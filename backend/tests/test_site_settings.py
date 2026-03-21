"""Tests for site settings endpoints — about intro photo and bio."""

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.about"
_SVC = "app.services.site_settings"
_STORAGE = "app.core.storage"


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestGetAboutIntro:
    @pytest.mark.anyio
    async def test_get_intro_member(self, client):
        """GET /about/intro by MEMBER → 200."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_SVC}.get_about_intro",
                new_callable=AsyncMock,
                return_value={"photo_key": "", "bio": "Hello"},
            ):
                resp = await client.get(
                    "/api/v1/about/intro",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["bio"] == "Hello"
            assert data["photo_url"] == ""
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_intro_with_photo(self, client):
        """GET /about/intro with photo_key → returns presigned URL."""
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_SVC}.get_about_intro",
                    new_callable=AsyncMock,
                    return_value={"photo_key": "site/photo.jpg", "bio": "Bio"},
                ),
                patch(
                    f"{_STORAGE}.generate_presigned_url",
                    return_value="http://localhost:19000/photo.jpg",
                ),
            ):
                resp = await client.get(
                    "/api/v1/about/intro",
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            assert resp.json()["photo_url"] == "http://localhost:19000/photo.jpg"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_intro_guest_forbidden(self, client):
        """GET /about/intro by GUEST → 403."""
        try:
            _override_auth("GUEST")
            resp = await client.get(
                "/api/v1/about/intro",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()


class TestUpdateAboutIntroPhoto:
    @pytest.mark.anyio
    async def test_upload_photo_super_admin(self, client):
        """PUT /about/admin/intro/photo by SUPER_ADMIN → 200."""
        try:
            _override_auth("SUPER_ADMIN")
            fake_file = BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
            with (
                patch(f"{_STORAGE}.upload_file", return_value="site/about-intro-test.jpg"),
                patch(f"{_STORAGE}.delete_file"),
                patch(
                    f"{_SVC}.get_about_intro",
                    new_callable=AsyncMock,
                    return_value={"photo_key": "site/old.jpg", "bio": ""},
                ),
                patch(
                    f"{_SVC}.update_about_intro_photo",
                    new_callable=AsyncMock,
                ),
                patch(
                    f"{_STORAGE}.generate_presigned_url",
                    return_value="http://localhost:19000/photo.jpg",
                ),
            ):
                resp = await client.put(
                    "/api/v1/about/admin/intro/photo",
                    files={"file": ("photo.jpg", fake_file, "image/jpeg")},
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            assert "photo_url" in resp.json()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_photo_deletes_old_file(self, client):
        """PUT /about/admin/intro/photo deletes previous photo from storage."""
        try:
            _override_auth("SUPER_ADMIN")
            fake_file = BytesIO(b"\x89PNG" + b"\x00" * 100)
            mock_delete = patch(f"{_STORAGE}.delete_file")
            with (
                patch(f"{_STORAGE}.upload_file"),
                mock_delete as m_del,
                patch(
                    f"{_SVC}.get_about_intro",
                    new_callable=AsyncMock,
                    return_value={"photo_key": "site/old-photo.png", "bio": ""},
                ),
                patch(f"{_SVC}.update_about_intro_photo", new_callable=AsyncMock),
                patch(f"{_STORAGE}.generate_presigned_url", return_value="http://x/new.png"),
            ):
                resp = await client.put(
                    "/api/v1/about/admin/intro/photo",
                    files={"file": ("photo.png", fake_file, "image/png")},
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            m_del.assert_called_once_with("site/old-photo.png")
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_invalid_magic_bytes_rejected(self, client):
        """PUT /about/admin/intro/photo with wrong magic bytes → 422."""
        try:
            _override_auth("SUPER_ADMIN")
            fake_file = BytesIO(b"GIF89a" + b"\x00" * 100)
            resp = await client.put(
                "/api/v1/about/admin/intro/photo",
                files={"file": ("photo.jpg", fake_file, "image/jpeg")},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_photo_non_admin_forbidden(self, client):
        """PUT /about/admin/intro/photo by ADMIN → 403."""
        try:
            _override_auth("ADMIN")
            fake_file = BytesIO(b"\x00" * 10)
            resp = await client.put(
                "/api/v1/about/admin/intro/photo",
                files={"file": ("photo.jpg", fake_file, "image/jpeg")},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_upload_invalid_type_rejected(self, client):
        """PUT /about/admin/intro/photo with text/plain → 422."""
        try:
            _override_auth("SUPER_ADMIN")
            fake_file = BytesIO(b"not an image")
            resp = await client.put(
                "/api/v1/about/admin/intro/photo",
                files={"file": ("doc.txt", fake_file, "text/plain")},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()


class TestUpdateAboutIntroBio:
    @pytest.mark.anyio
    async def test_update_bio_super_admin(self, client):
        """PUT /about/admin/intro/bio by SUPER_ADMIN → 200."""
        try:
            _override_auth("SUPER_ADMIN")
            with patch(
                f"{_SVC}.update_about_intro_bio",
                new_callable=AsyncMock,
            ):
                resp = await client.put(
                    "/api/v1/about/admin/intro/bio",
                    json={"bio": "New bio text"},
                    headers={"Authorization": "Bearer fake"},
                )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_bio_non_admin_forbidden(self, client):
        """PUT /about/admin/intro/bio by MEMBER → 403."""
        try:
            _override_auth("MEMBER")
            resp = await client.put(
                "/api/v1/about/admin/intro/bio",
                json={"bio": "test"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_update_bio_too_long_rejected(self, client):
        """PUT /about/admin/intro/bio with >5000 chars → 422."""
        try:
            _override_auth("SUPER_ADMIN")
            resp = await client.put(
                "/api/v1/about/admin/intro/bio",
                json={"bio": "x" * 5001},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 422
        finally:
            _clear_overrides()
