"""Unit tests for the storage module (app.core.storage).

Covers: generate_presigned_url, upload_file, delete_file, get_file_size,
init_storage bucket creation, and MINIO_PUBLIC_URL rewriting.
"""

from unittest.mock import MagicMock, patch

import pytest

# Module path for patching
_STORAGE = "app.core.storage"


class TestGeneratePresignedUrl:
    """generate_presigned_url() generates a URL (mock boto3 client)."""

    def test_basic_url_generation(self):
        """Generates a presigned URL using the internal client."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = (
            "http://minio:9000/bucket/key?signature=abc"
        )

        with (
            patch(f"{_STORAGE}._s3_presign_client", None),
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"

            from app.core.storage import generate_presigned_url

            url = generate_presigned_url("avatars/user1/img.png")

        assert url == "http://minio:9000/bucket/key?signature=abc"
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "avatars/user1/img.png"},
            ExpiresIn=3600,
        )

    def test_custom_expires_in(self):
        """ExpiresIn parameter is forwarded."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "http://url"

        with (
            patch(f"{_STORAGE}._s3_presign_client", None),
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "bucket"

            from app.core.storage import generate_presigned_url

            generate_presigned_url("key", expires_in=7200)

        call_kwargs = mock_client.generate_presigned_url.call_args
        assert call_kwargs[1]["ExpiresIn"] == 7200 or call_kwargs[0][2] == 7200


class TestPresignedUrlWithFilename:
    """generate_presigned_url() with filename sets Content-Disposition."""

    def test_filename_sets_content_disposition(self):
        """When filename is provided, ResponseContentDisposition is added."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "http://url"

        with (
            patch(f"{_STORAGE}._s3_presign_client", None),
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "bucket"

            from app.core.storage import generate_presigned_url

            generate_presigned_url("key", filename="report.pdf")

        call_args = mock_client.generate_presigned_url.call_args
        params = call_args[1]["Params"] if "Params" in call_args[1] else call_args[0][1]
        assert "ResponseContentDisposition" in params
        assert "report.pdf" in params["ResponseContentDisposition"]

    def test_non_ascii_filename_sanitized(self):
        """Non-ASCII characters in filename are replaced with underscore."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "http://url"

        with (
            patch(f"{_STORAGE}._s3_presign_client", None),
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "bucket"

            from app.core.storage import generate_presigned_url

            generate_presigned_url("key", filename="报告.pdf")

        call_args = mock_client.generate_presigned_url.call_args
        params = call_args[1]["Params"] if "Params" in call_args[1] else call_args[0][1]
        disp = params["ResponseContentDisposition"]
        # Non-ASCII characters should be replaced
        assert "报告" not in disp
        assert ".pdf" in disp


class TestPresignedUrlPublicRewrite:
    """generate_presigned_url() uses presign client when MINIO_PUBLIC_URL is set."""

    def test_uses_presign_client_when_available(self):
        """When _s3_presign_client is set, it is used instead of _s3_client."""
        mock_internal = MagicMock()
        mock_presign = MagicMock()
        mock_presign.generate_presigned_url.return_value = (
            "http://localhost:19000/bucket/key?signature=xyz"
        )

        with (
            patch(f"{_STORAGE}._s3_presign_client", mock_presign),
            patch(f"{_STORAGE}._s3_client", mock_internal),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "bucket"

            from app.core.storage import generate_presigned_url

            url = generate_presigned_url("key")

        assert "localhost:19000" in url
        mock_presign.generate_presigned_url.assert_called_once()
        mock_internal.generate_presigned_url.assert_not_called()


class TestUploadFile:
    """upload_file() calls put_object."""

    def test_put_object_called(self):
        """upload_file calls client.put_object with correct params."""
        mock_client = MagicMock()

        with (
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"

            from app.core.storage import upload_file

            result = upload_file(b"file-data", "uploads/file.txt", "text/plain")

        assert result == "uploads/file.txt"
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "uploads/file.txt"
        assert call_kwargs["ContentLength"] == 9
        assert call_kwargs["ContentType"] == "text/plain"


class TestDeleteFile:
    """delete_file() calls remove_object."""

    def test_delete_object_called(self):
        """delete_file calls client.delete_object with correct params."""
        mock_client = MagicMock()

        with (
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"

            from app.core.storage import delete_file

            delete_file("uploads/file.txt")

        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="uploads/file.txt"
        )


class TestGetFileSize:
    """get_file_size() returns correct size."""

    def test_returns_content_length(self):
        """get_file_size returns ContentLength from head_object response."""
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 12345}

        with (
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"

            from app.core.storage import get_file_size

            size = get_file_size("uploads/file.txt")

        assert size == 12345

    def test_returns_0_on_404(self):
        """get_file_size returns 0 when the object is not found (404)."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_client.head_object.side_effect = ClientError(error_response, "HeadObject")

        with (
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"

            from app.core.storage import get_file_size

            size = get_file_size("nonexistent/file.txt")

        assert size == 0

    def test_raises_on_other_errors(self):
        """get_file_size re-raises non-404 ClientError."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        error_response = {"Error": {"Code": "403", "Message": "Forbidden"}}
        mock_client.head_object.side_effect = ClientError(error_response, "HeadObject")

        with (
            patch(f"{_STORAGE}._s3_client", mock_client),
            patch(f"{_STORAGE}.settings") as mock_settings,
        ):
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"

            from app.core.storage import get_file_size

            with pytest.raises(ClientError):
                get_file_size("forbidden/file.txt")


class TestInitStorage:
    """Storage init creates bucket if not exists."""

    def test_creates_bucket_when_missing(self):
        """init_storage creates the bucket when head_bucket raises ClientError."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_client.head_bucket.side_effect = ClientError(error_response, "HeadBucket")
        mock_client.exceptions.ClientError = ClientError

        with (
            patch(f"{_STORAGE}.boto3") as mock_boto3,
            patch(f"{_STORAGE}.settings") as mock_settings,
            patch(f"{_STORAGE}._s3_client", None),
            patch(f"{_STORAGE}._s3_presign_client", None),
        ):
            mock_boto3.client.return_value = mock_client
            mock_settings.MINIO_USE_SSL = False
            mock_settings.MINIO_ENDPOINT = "minio:9000"
            mock_settings.MINIO_ROOT_USER = "admin"
            mock_settings.MINIO_ROOT_PASSWORD = "password"
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"
            mock_settings.MINIO_PUBLIC_URL = ""

            from app.core.storage import init_storage

            init_storage()

        mock_client.create_bucket.assert_called_once_with(Bucket="test-bucket")

    def test_skips_creation_when_bucket_exists(self):
        """init_storage does not create bucket when head_bucket succeeds."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}

        with (
            patch(f"{_STORAGE}.boto3") as mock_boto3,
            patch(f"{_STORAGE}.settings") as mock_settings,
            patch(f"{_STORAGE}._s3_client", None),
            patch(f"{_STORAGE}._s3_presign_client", None),
        ):
            mock_boto3.client.return_value = mock_client
            mock_settings.MINIO_USE_SSL = False
            mock_settings.MINIO_ENDPOINT = "minio:9000"
            mock_settings.MINIO_ROOT_USER = "admin"
            mock_settings.MINIO_ROOT_PASSWORD = "password"
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"
            mock_settings.MINIO_PUBLIC_URL = ""

            from app.core.storage import init_storage

            init_storage()

        mock_client.create_bucket.assert_not_called()

    def test_creates_presign_client_when_public_url_set(self):
        """init_storage creates _s3_presign_client when MINIO_PUBLIC_URL is set."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}

        clients_created = []

        def track_client(*args, **kwargs):
            client = MagicMock()
            client.head_bucket.return_value = {}
            client.exceptions.ClientError = Exception
            clients_created.append(kwargs.get("endpoint_url", ""))
            return client

        with (
            patch(f"{_STORAGE}.boto3") as mock_boto3,
            patch(f"{_STORAGE}.settings") as mock_settings,
            patch(f"{_STORAGE}._s3_client", None),
            patch(f"{_STORAGE}._s3_presign_client", None),
        ):
            mock_boto3.client.side_effect = track_client
            mock_settings.MINIO_USE_SSL = False
            mock_settings.MINIO_ENDPOINT = "minio:9000"
            mock_settings.MINIO_ROOT_USER = "admin"
            mock_settings.MINIO_ROOT_PASSWORD = "password"
            mock_settings.MINIO_BUCKET_NAME = "test-bucket"
            mock_settings.MINIO_PUBLIC_URL = "http://localhost:19000"

            from app.core.storage import init_storage

            init_storage()

        # Two clients should have been created: internal + presign
        assert len(clients_created) == 2
        assert "http://localhost:19000" in clients_created


class TestGetStorage:
    """get_storage() raises RuntimeError when not initialized."""

    def test_raises_when_not_initialized(self):
        """get_storage raises RuntimeError when _s3_client is None."""
        with patch(f"{_STORAGE}._s3_client", None):
            from app.core.storage import get_storage

            with pytest.raises(RuntimeError, match="not initialized"):
                get_storage()


class TestCloseStorage:
    """close_storage() cleans up both clients."""

    def test_closes_both_clients(self):
        """close_storage closes _s3_client and _s3_presign_client."""
        mock_main = MagicMock()
        mock_presign = MagicMock()

        with (
            patch(f"{_STORAGE}._s3_client", mock_main),
            patch(f"{_STORAGE}._s3_presign_client", mock_presign),
        ):
            from app.core.storage import close_storage

            close_storage()

        mock_main.close.assert_called_once()
        mock_presign.close.assert_called_once()

    def test_handles_none_clients(self):
        """close_storage does not crash when clients are already None."""
        with (
            patch(f"{_STORAGE}._s3_client", None),
            patch(f"{_STORAGE}._s3_presign_client", None),
        ):
            from app.core.storage import close_storage

            # Should not raise
            close_storage()


class TestHelperKeyGenerators:
    """Key generation helpers produce correct path formats."""

    def test_avatar_key_format(self):
        from app.core.storage import generate_avatar_key

        key = generate_avatar_key("user123", ".png")
        assert key.startswith("avatars/user123/")
        assert key.endswith(".png")

    def test_form_banner_key_format(self):
        from app.core.storage import generate_form_banner_key

        key = generate_form_banner_key("form456", ".jpg")
        assert key.startswith("forms/banners/form456/")
        assert key.endswith(".jpg")

    def test_form_upload_key_format(self):
        from app.core.storage import generate_form_upload_key

        key = generate_form_upload_key("form789", ".pdf")
        assert key.startswith("forms/uploads/form789/")
        assert key.endswith(".pdf")

    def test_form_export_key_format(self):
        from app.core.storage import generate_form_export_key

        key = generate_form_export_key("form000", "task111")
        assert key == "exports/forms/form000/task111.csv"
