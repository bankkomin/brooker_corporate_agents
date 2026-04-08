"""SFTP connector stub — to be implemented when SFTP access is available."""

from pathlib import Path

from .base import BaseConnector, RemoteFile


class SFTPConnector(BaseConnector):
    """SFTP connector (stub)."""

    async def list_files(self) -> list[RemoteFile]:
        raise NotImplementedError("SFTP connector not yet implemented")

    async def download_file(self, remote_path: str, local_path: Path) -> None:
        raise NotImplementedError("SFTP connector not yet implemented")

    async def get_file_hash(self, remote_path: str) -> str:
        raise NotImplementedError("SFTP connector not yet implemented")
