"""SHA-256 hash manifest management for change detection."""

import json
from datetime import UTC, datetime
from pathlib import Path

from .connectors.base import RemoteFile


class HashChecker:
    """Manages .sync_manifest.json for detecting file changes."""

    def __init__(self, mirror_path: Path) -> None:
        self._mirror_path = Path(mirror_path)
        self._manifest: dict[str, dict[str, str | int]] = {}
        self._load_manifest()

    @property
    def manifest_path(self) -> Path:
        return self._mirror_path / ".sync_manifest.json"

    def _load_manifest(self) -> None:
        if self.manifest_path.exists():
            with open(self.manifest_path) as f:
                data = json.load(f)
            self._manifest = data.get("files", {})
        else:
            self._manifest = {}

    def save_manifest(self) -> None:
        data = {
            "last_sync": datetime.now(UTC).isoformat(),
            "files": self._manifest,
        }
        self._mirror_path.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_known_files(self) -> dict[str, dict[str, str | int]]:
        return dict(self._manifest)

    def update_file(self, path: str, file_hash: str, size_bytes: int) -> None:
        self._manifest[path] = {
            "hash": file_hash,
            "size_bytes": size_bytes,
            "synced_at": datetime.now(UTC).isoformat(),
        }

    def remove_file(self, path: str) -> None:
        self._manifest.pop(path, None)

    def get_changed_files(self, remote_files: list[RemoteFile]) -> list[RemoteFile]:
        changed: list[RemoteFile] = []
        for rf in remote_files:
            known = self._manifest.get(rf.path)
            if known is None or known["hash"] != rf.hash:
                changed.append(rf)
        return changed
