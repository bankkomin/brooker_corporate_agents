"""Tests for SHA-256 hash manifest management."""

from pathlib import Path

from services.sync_mirror.src.connectors.base import RemoteFile
from services.sync_mirror.src.hash_check import HashChecker


class TestHashChecker:
    def test_load_empty_manifest(self, tmp_path: Path) -> None:
        """No manifest file → empty state."""
        checker = HashChecker(mirror_path=tmp_path)
        assert checker.get_known_files() == {}

    def test_save_and_load_manifest(self, tmp_path: Path) -> None:
        """Manifest round-trips through JSON correctly."""
        checker = HashChecker(mirror_path=tmp_path)
        checker.update_file("excel/data.xlsx", "sha256:abc123", 1024)
        checker.save_manifest()

        checker2 = HashChecker(mirror_path=tmp_path)
        files = checker2.get_known_files()
        assert "excel/data.xlsx" in files
        assert files["excel/data.xlsx"]["hash"] == "sha256:abc123"
        assert files["excel/data.xlsx"]["size_bytes"] == 1024

    def test_detect_new_file(self, tmp_path: Path) -> None:
        checker = HashChecker(mirror_path=tmp_path)
        remote = RemoteFile(path="new.pdf", hash="sha256:xyz", size_bytes=512)
        changed = checker.get_changed_files([remote])
        assert len(changed) == 1
        assert changed[0].path == "new.pdf"

    def test_detect_changed_file(self, tmp_path: Path) -> None:
        checker = HashChecker(mirror_path=tmp_path)
        checker.update_file("doc.pdf", "sha256:old_hash", 1024)
        remote = RemoteFile(path="doc.pdf", hash="sha256:new_hash", size_bytes=2048)
        changed = checker.get_changed_files([remote])
        assert len(changed) == 1

    def test_skip_unchanged_file(self, tmp_path: Path) -> None:
        checker = HashChecker(mirror_path=tmp_path)
        checker.update_file("same.pdf", "sha256:same_hash", 1024)
        remote = RemoteFile(path="same.pdf", hash="sha256:same_hash", size_bytes=1024)
        changed = checker.get_changed_files([remote])
        assert len(changed) == 0

    def test_manifest_file_path(self, tmp_path: Path) -> None:
        checker = HashChecker(mirror_path=tmp_path)
        assert checker.manifest_path == tmp_path / ".sync_manifest.json"

    def test_remove_file_from_manifest(self, tmp_path: Path) -> None:
        checker = HashChecker(mirror_path=tmp_path)
        checker.update_file("old.pdf", "sha256:abc", 1024)
        checker.remove_file("old.pdf")
        assert "old.pdf" not in checker.get_known_files()
