"""Unit tests for Slack image upload — MinIO routing and file_handler integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# image_upload module — pure-function tests (no I/O)
# ---------------------------------------------------------------------------


class TestBuildMinioKey:
    def test_build_minio_key_format(self) -> None:
        from services.slack_bot.src.image_upload import build_minio_key

        key = build_minio_key("C123", "FABC", "photo.png")
        assert key == "slack-uploads/C123/FABC-photo.png"

    def test_build_minio_key_sanitises_forward_slashes(self) -> None:
        from services.slack_bot.src.image_upload import build_minio_key

        key = build_minio_key("C001", "F999", "sub/dir/image.jpg")
        # Forward slashes in filename become underscores
        assert key == "slack-uploads/C001/F999-sub_dir_image.jpg"

    def test_build_minio_key_sanitises_back_slashes(self) -> None:
        from services.slack_bot.src.image_upload import build_minio_key

        key = build_minio_key("C001", "F888", "win\\path\\image.jpeg")
        assert key == "slack-uploads/C001/F888-win_path_image.jpeg"


# ---------------------------------------------------------------------------
# upload_image_to_minio — behaviour with a mocked Minio client
# ---------------------------------------------------------------------------


class TestUploadImageToMinio:
    def _make_client(self) -> MagicMock:
        """Minio client mock with bucket_exists returning False (triggers creation)."""
        client = MagicMock()
        client.bucket_exists.return_value = False
        client.put_object.return_value = None
        return client

    def test_calls_ensure_bucket_then_put_object(self) -> None:
        """ensure_bucket (make_bucket) must be called before put_object."""
        from services.slack_bot.src.image_upload import upload_image_to_minio

        client = self._make_client()
        upload_image_to_minio(
            file_bytes=b"\x89PNGfakedata",
            filename="test.png",
            filetype="png",
            channel_id="C001",
            file_id="F001",
            client=client,
            bucket="paperclip-uploads",
        )

        # bucket_exists checked, then make_bucket called, then put_object
        client.bucket_exists.assert_called_once_with("paperclip-uploads")
        client.make_bucket.assert_called_once_with("paperclip-uploads")
        assert client.put_object.call_count == 1

        # Verify call order: make_bucket must precede put_object
        make_idx = [c[0] for c in client.method_calls].index("make_bucket")
        put_idx = [c[0] for c in client.method_calls].index("put_object")
        assert make_idx < put_idx

    def test_skips_make_bucket_when_bucket_exists(self) -> None:
        from services.slack_bot.src.image_upload import upload_image_to_minio

        client = self._make_client()
        client.bucket_exists.return_value = True

        upload_image_to_minio(
            file_bytes=b"data",
            filename="x.gif",
            filetype="gif",
            channel_id="C002",
            file_id="F002",
            client=client,
        )

        client.make_bucket.assert_not_called()
        client.put_object.assert_called_once()

    def test_sets_content_type_png(self) -> None:
        from services.slack_bot.src.image_upload import upload_image_to_minio

        client = self._make_client()
        upload_image_to_minio(
            file_bytes=b"data",
            filename="shot.png",
            filetype="png",
            channel_id="C1",
            file_id="F1",
            client=client,
        )

        _, kwargs = client.put_object.call_args
        assert kwargs["content_type"] == "image/png"

    def test_sets_content_type_jpg_as_jpeg(self) -> None:
        """Slack sends filetype='jpg'; MIME must be image/jpeg."""
        from services.slack_bot.src.image_upload import upload_image_to_minio

        client = self._make_client()
        upload_image_to_minio(
            file_bytes=b"data",
            filename="photo.jpg",
            filetype="jpg",
            channel_id="C1",
            file_id="F1",
            client=client,
        )

        _, kwargs = client.put_object.call_args
        assert kwargs["content_type"] == "image/jpeg"

    def test_sets_content_type_jpeg(self) -> None:
        from services.slack_bot.src.image_upload import upload_image_to_minio

        client = self._make_client()
        upload_image_to_minio(
            file_bytes=b"data",
            filename="photo.jpeg",
            filetype="jpeg",
            channel_id="C1",
            file_id="F1",
            client=client,
        )

        _, kwargs = client.put_object.call_args
        assert kwargs["content_type"] == "image/jpeg"

    def test_returns_expected_dict_shape(self) -> None:
        from services.slack_bot.src.image_upload import upload_image_to_minio

        client = self._make_client()
        result = upload_image_to_minio(
            file_bytes=b"somedata",
            filename="chart.png",
            filetype="png",
            channel_id="C42",
            file_id="FXYZ",
            client=client,
            bucket="paperclip-uploads",
        )

        assert result["minio_key"] == "slack-uploads/C42/FXYZ-chart.png"
        assert result["filename"] == "chart.png"
        assert result["file_id"] == "FXYZ"
        assert result["bucket"] == "paperclip-uploads"
        assert result["size"] == len(b"somedata")

    def test_put_object_receives_correct_key_and_length(self) -> None:
        from services.slack_bot.src.image_upload import upload_image_to_minio

        client = self._make_client()
        data = b"x" * 100
        upload_image_to_minio(
            file_bytes=data,
            filename="img.gif",
            filetype="gif",
            channel_id="CCHAN",
            file_id="FFILE",
            client=client,
        )

        _, kwargs = client.put_object.call_args
        assert kwargs["object_name"] == "slack-uploads/CCHAN/FFILE-img.gif"
        assert kwargs["length"] == 100


# ---------------------------------------------------------------------------
# file_handler.download_and_forward_file — routing tests
# ---------------------------------------------------------------------------


class TestFileHandlerRouting:
    def _make_file_info(self, filetype: str, name: str = "file.dat"):
        from services.slack_bot.src.models import SlackFileInfo

        return SlackFileInfo(
            id="F_TEST",
            name=name,
            mimetype=f"image/{filetype}" if filetype in {"png", "jpg", "jpeg", "gif"} else "application/octet-stream",
            url_private_download="https://files.slack.com/test",
            size=1024,
            filetype=filetype,
        )

    @pytest.mark.asyncio
    async def test_routes_image_to_minio_not_rag(self) -> None:
        """PNG file must call upload_image_to_minio and NOT call rag_client.upload_file."""
        from services.slack_bot.src.file_handler import download_and_forward_file

        file_info = self._make_file_info("png", "screenshot.png")
        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock()

        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.put_object.return_value = None

        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = b"\x89PNGfakedata"
        mock_resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_resp)

        result = await download_and_forward_file(
            file_info=file_info,
            channel_id="C_IMG",
            bot_token="xoxb-test",
            rag_client=mock_rag,
            http=mock_http,
            minio_client=mock_minio,
        )

        # rag-ingestion must NOT be touched
        mock_rag.upload_file.assert_not_called()

        # MinIO put_object must have been called
        mock_minio.put_object.assert_called_once()

        # Result contract
        assert result["status"] == "uploaded_image"
        assert "minio_key" in result
        assert result["minio_key"].startswith("slack-uploads/C_IMG/")
        assert result["filename"] == "screenshot.png"
        assert result["file_id"] == "F_TEST"
        assert result["bucket"] == "paperclip-uploads"

    @pytest.mark.asyncio
    async def test_routes_pdf_to_rag_unchanged(self) -> None:
        """Regression: PDF must still go to rag-ingestion, MinIO untouched."""
        from services.slack_bot.src.file_handler import download_and_forward_file

        file_info = self._make_file_info("pdf", "minutes.pdf")
        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock(return_value={"status": "ingested", "chunks": 7})

        mock_minio = MagicMock()

        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = b"%PDF-1.4 fake"
        mock_resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_resp)

        result = await download_and_forward_file(
            file_info=file_info,
            channel_id="C_DOC",
            bot_token="xoxb-test",
            rag_client=mock_rag,
            http=mock_http,
            minio_client=mock_minio,
        )

        mock_rag.upload_file.assert_called_once()
        mock_minio.put_object.assert_not_called()
        assert result["status"] == "ingested"
        assert result["chunks"] == 7

    @pytest.mark.asyncio
    async def test_rejects_unsupported_type(self) -> None:
        """Filetype not in ALL_ACCEPTED must be skipped without any network call."""
        from services.slack_bot.src.file_handler import download_and_forward_file

        file_info = self._make_file_info("exe", "malware.exe")
        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock()
        mock_minio = MagicMock()

        result = await download_and_forward_file(
            file_info=file_info,
            channel_id="C_BAD",
            bot_token="xoxb-test",
            rag_client=mock_rag,
            minio_client=mock_minio,
        )

        assert result["status"] == "skipped"
        assert "unsupported type" in result["reason"]
        mock_rag.upload_file.assert_not_called()
        mock_minio.put_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_jpg_routes_to_minio(self) -> None:
        """jpg (Slack's filetype for JPEG) also routes to MinIO."""
        from services.slack_bot.src.file_handler import download_and_forward_file

        file_info = self._make_file_info("jpg", "photo.jpg")
        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock()

        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True
        mock_minio.put_object.return_value = None

        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = b"\xff\xd8\xff fakedata"
        mock_resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_resp)

        result = await download_and_forward_file(
            file_info=file_info,
            channel_id="C_JPG",
            bot_token="xoxb-test",
            rag_client=mock_rag,
            http=mock_http,
            minio_client=mock_minio,
        )

        assert result["status"] == "uploaded_image"
        mock_rag.upload_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_image_too_large_is_skipped(self) -> None:
        """Images over the size cap should be skipped before any I/O."""
        from services.slack_bot.src.file_handler import download_and_forward_file
        from services.slack_bot.src.models import SlackFileInfo

        big_file = SlackFileInfo(
            id="F_BIG",
            name="huge.png",
            mimetype="image/png",
            url_private_download="https://files.slack.com/huge.png",
            size=60 * 1024 * 1024,  # 60 MB — over the 50 MB cap
            filetype="png",
        )

        result = await download_and_forward_file(
            file_info=big_file,
            channel_id="C_BIG",
            bot_token="xoxb-test",
            rag_client=MagicMock(),
        )

        assert result["status"] == "skipped"
        assert "too large" in result["reason"]
