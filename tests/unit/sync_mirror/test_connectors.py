"""Tests for mirror source connectors."""

import pytest
from services.sync_mirror.src.connectors.base import BaseConnector, RemoteFile
from services.sync_mirror.src.connectors.sftp import SFTPConnector
from services.sync_mirror.src.connectors.sharepoint import SharePointConnector


class TestRemoteFile:
    def test_remote_file_is_frozen(self) -> None:
        rf = RemoteFile(path="test.pdf", hash="sha256:abc", size_bytes=1024)
        with pytest.raises(AttributeError):
            rf.path = "other.pdf"  # type: ignore[misc]

    def test_remote_file_fields(self) -> None:
        rf = RemoteFile(path="excel/data.xlsx", hash="sha256:def", size_bytes=2048)
        assert rf.path == "excel/data.xlsx"
        assert rf.hash == "sha256:def"
        assert rf.size_bytes == 2048


class TestBaseConnector:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            BaseConnector()  # type: ignore[abstract]


class TestSharePointConnector:
    @pytest.mark.asyncio
    async def test_list_files_raises_not_implemented(self) -> None:
        conn = SharePointConnector()
        with pytest.raises(NotImplementedError, match="SharePoint"):
            await conn.list_files()

    @pytest.mark.asyncio
    async def test_download_file_raises_not_implemented(self) -> None:
        conn = SharePointConnector()
        with pytest.raises(NotImplementedError, match="SharePoint"):
            await conn.download_file("test.pdf", "/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_get_file_hash_raises_not_implemented(self) -> None:
        conn = SharePointConnector()
        with pytest.raises(NotImplementedError, match="SharePoint"):
            await conn.get_file_hash("test.pdf")


class TestSFTPConnector:
    @pytest.mark.asyncio
    async def test_list_files_raises_not_implemented(self) -> None:
        conn = SFTPConnector()
        with pytest.raises(NotImplementedError, match="SFTP"):
            await conn.list_files()

    @pytest.mark.asyncio
    async def test_download_file_raises_not_implemented(self) -> None:
        conn = SFTPConnector()
        with pytest.raises(NotImplementedError, match="SFTP"):
            await conn.download_file("test.pdf", "/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_get_file_hash_raises_not_implemented(self) -> None:
        conn = SFTPConnector()
        with pytest.raises(NotImplementedError, match="SFTP"):
            await conn.get_file_hash("test.pdf")
