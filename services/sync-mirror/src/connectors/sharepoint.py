"""SharePoint connector stub — to be implemented when SharePoint access is available."""

from pathlib import Path

from .base import BaseConnector, RemoteFile


class SharePointConnector(BaseConnector):
    """SharePoint Online connector (stub)."""

    async def list_files(self) -> list[RemoteFile]:
        raise NotImplementedError("SharePoint connector not yet implemented")

    async def download_file(self, remote_path: str, local_path: Path) -> None:
        raise NotImplementedError("SharePoint connector not yet implemented")

    async def get_file_hash(self, remote_path: str) -> str:
        raise NotImplementedError("SharePoint connector not yet implemented")
