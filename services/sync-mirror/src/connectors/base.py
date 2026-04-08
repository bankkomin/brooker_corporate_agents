"""Abstract base class for mirror source connectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RemoteFile:
    """Represents a file on the remote source."""

    path: str
    hash: str
    size_bytes: int


class BaseConnector(ABC):
    """Abstract base for all mirror source connectors."""

    @abstractmethod
    async def list_files(self) -> list[RemoteFile]:
        """List all files at the source with their hashes."""

    @abstractmethod
    async def download_file(self, remote_path: str, local_path: Path) -> None:
        """Download a single file from source to local mirror path."""

    @abstractmethod
    async def get_file_hash(self, remote_path: str) -> str:
        """Get SHA-256 hash of a remote file for change detection."""
