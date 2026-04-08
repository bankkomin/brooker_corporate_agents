"""Tests for Slack file download and forwarding."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestDownloadAndForwardFile:
    @pytest.fixture
    def file_info(self):
        from services.slack_bot.src.models import SlackFileInfo

        return SlackFileInfo(
            id="F12345",
            name="alco_minutes.pdf",
            mimetype="application/pdf",
            url_private_download="https://files.slack.com/files/alco_minutes.pdf",
            size=204800,
            filetype="pdf",
        )

    @pytest.mark.asyncio
    async def test_download_and_forward_success(self, file_info) -> None:
        from services.slack_bot.src.file_handler import download_and_forward_file

        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock(return_value={"status": "ingested", "chunks": 12})

        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = b"%PDF-1.4 fake content"
        mock_resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_resp)

        result = await download_and_forward_file(
            file_info=file_info,
            channel_id="C123",
            bot_token="xoxb-test",
            rag_client=mock_rag,
            http=mock_http,
        )
        assert result["status"] == "ingested"

    @pytest.mark.asyncio
    async def test_unsupported_filetype_skipped(self) -> None:
        from services.slack_bot.src.file_handler import download_and_forward_file
        from services.slack_bot.src.models import SlackFileInfo

        f = SlackFileInfo(
            id="F999", name="image.png", mimetype="image/png",
            url_private_download="https://files.slack.com/image.png",
            size=100, filetype="png",
        )
        result = await download_and_forward_file(
            file_info=f,
            channel_id="C123",
            bot_token="xoxb-test",
            rag_client=MagicMock(),
        )
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up_on_success(self, file_info) -> None:
        from services.slack_bot.src.file_handler import download_and_forward_file

        created_paths: list[Path] = []

        async def mock_download(file_info, bot_token, http):
            import tempfile
            tmp = Path(tempfile.mktemp(suffix=".pdf"))
            tmp.write_bytes(b"fake pdf")
            created_paths.append(tmp)
            return tmp

        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock(return_value={"status": "ingested", "chunks": 5})

        patch_target = "services.slack_bot.src.file_handler._download_to_temp"
        with patch(patch_target, side_effect=mock_download):
            await download_and_forward_file(
                file_info=file_info,
                channel_id="C123",
                bot_token="xoxb-test",
                rag_client=mock_rag,
            )

        for p in created_paths:
            assert not p.exists(), f"Temp file {p} was not cleaned up"

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up_on_upload_failure(self, file_info) -> None:
        from services.slack_bot.src.file_handler import download_and_forward_file

        created_paths: list[Path] = []

        async def mock_download(file_info, bot_token, http):
            import tempfile
            tmp = Path(tempfile.mktemp(suffix=".pdf"))
            tmp.write_bytes(b"fake pdf")
            created_paths.append(tmp)
            return tmp

        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock(side_effect=httpx.ConnectError("down"))

        patch_target = "services.slack_bot.src.file_handler._download_to_temp"
        with patch(patch_target, side_effect=mock_download), pytest.raises(httpx.ConnectError):
            await download_and_forward_file(
                file_info=file_info,
                channel_id="C123",
                bot_token="xoxb-test",
                rag_client=mock_rag,
            )

        for p in created_paths:
            assert not p.exists(), f"Temp file {p} was not cleaned up after failure"

    @pytest.mark.asyncio
    async def test_download_uses_auth_header(self, file_info) -> None:
        from services.slack_bot.src.file_handler import _download_to_temp

        mock_resp = MagicMock()
        mock_resp.content = b"file bytes"
        mock_resp.raise_for_status = MagicMock()
        http = MagicMock()
        http.get = AsyncMock(return_value=mock_resp)

        tmp = await _download_to_temp(file_info, "xoxb-secret", http)
        try:
            call_kwargs = http.get.call_args
            headers = call_kwargs[1].get("headers", {})
            assert headers.get("Authorization") == "Bearer xoxb-secret"
        finally:
            tmp.unlink(missing_ok=True)
