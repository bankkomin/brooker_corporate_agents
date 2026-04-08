# tests/unit/rag_ingestion/test_vault_watcher.py
"""Tests for Obsidian vault watcher."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.rag_ingestion.src.chunker import TextChunk
from services.rag_ingestion.src.vault_watcher import (
    KNOWLEDGE_COLLECTION,
    VaultWatcher,
    _VaultEventHandler,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings(tmp_path: Path) -> MagicMock:
    s = MagicMock()
    s.obsidian_vault_path = "/tmp/test-vault"
    s.obsidian_ingest_delay_seconds = 0
    # Point at a non-existent path so _load_watch_config falls back gracefully
    s.obsidian_watch_config = str(tmp_path / "nonexistent_watch.json")
    return s


@pytest.fixture
def watch_config() -> dict:
    """Minimal watch config used by config-routing tests."""
    return {
        "watch_folders": [
            {"path": "cac/concepts/", "collection": "cac_knowledge", "doc_type": "concept"},
            {"path": "cac/decisions/", "collection": "cac_knowledge", "doc_type": "decision_log"},
            {
                "path": "shared/policies/",
                "collection": "shared_policies",
                "doc_type": "policy_note",
            },
            {"path": "hr/concepts/", "collection": "hr_knowledge", "doc_type": "concept"},
        ],
        "ignore_folders": [".obsidian", "templates", "archive"],
        "ignore_files": ["index.md", "log.md"],
    }


@pytest.fixture
def mock_settings_with_config(tmp_path: Path, watch_config: dict) -> MagicMock:
    """Settings fixture that writes a real watch config file."""
    config_file = tmp_path / "obsidian_watch.json"
    config_file.write_text(json.dumps(watch_config))

    s = MagicMock()
    s.obsidian_vault_path = str(tmp_path / "vault")
    s.obsidian_ingest_delay_seconds = 0
    s.obsidian_watch_config = str(config_file)
    return s


@pytest.fixture
def mock_chunker() -> AsyncMock:
    c = AsyncMock()
    c.chunk_file.return_value = [
        TextChunk("chunk 1", {"source_file": "/tmp/test.md", "doc_type": "md"}),
        TextChunk("chunk 2", {"source_file": "/tmp/test.md", "doc_type": "md"}),
    ]
    return c


@pytest.fixture
def mock_embedder() -> AsyncMock:
    e = AsyncMock()
    e.embed_texts.return_value = [[0.1] * 4, [0.2] * 4]
    return e


@pytest.fixture
def mock_store() -> AsyncMock:
    s = AsyncMock()
    s.upsert_chunks.return_value = 2
    return s


@pytest.fixture
def watcher(
    mock_settings: MagicMock,
    mock_chunker: AsyncMock,
    mock_embedder: AsyncMock,
    mock_store: AsyncMock,
) -> VaultWatcher:
    return VaultWatcher(
        settings=mock_settings,
        chunker=mock_chunker,
        embedder=mock_embedder,
        store=mock_store,
        postgres_dsn="postgresql://test:test@localhost/test",
    )


@pytest.fixture
def watcher_with_config(
    mock_settings_with_config: MagicMock,
    mock_chunker: AsyncMock,
    mock_embedder: AsyncMock,
    mock_store: AsyncMock,
) -> VaultWatcher:
    return VaultWatcher(
        settings=mock_settings_with_config,
        chunker=mock_chunker,
        embedder=mock_embedder,
        store=mock_store,
        postgres_dsn="postgresql://test:test@localhost/test",
    )


# ---------------------------------------------------------------------------
# TestLoadWatchConfig
# ---------------------------------------------------------------------------


class TestLoadWatchConfig:
    def test_missing_config_returns_empty_structure(self, watcher: VaultWatcher) -> None:
        """Config that doesn't exist yields empty watch_folders/ignore lists."""
        cfg = watcher._watch_config
        assert cfg["watch_folders"] == []
        assert cfg["ignore_folders"] == []
        assert cfg["ignore_files"] == []

    def test_valid_config_loaded(
        self, watcher_with_config: VaultWatcher, watch_config: dict
    ) -> None:
        """Valid config file is parsed and stored correctly."""
        assert len(watcher_with_config._watch_config["watch_folders"]) == len(
            watch_config["watch_folders"]
        )
        assert watcher_with_config._watch_config["ignore_folders"] == [
            ".obsidian",
            "templates",
            "archive",
        ]

    def test_invalid_json_falls_back(
        self, tmp_path: Path, mock_chunker, mock_embedder, mock_store  # noqa: ANN001
    ) -> None:
        """Malformed JSON triggers the fallback empty structure."""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text("{ not valid json }")

        s = MagicMock()
        s.obsidian_vault_path = str(tmp_path / "vault")
        s.obsidian_ingest_delay_seconds = 0
        s.obsidian_watch_config = str(bad_config)

        w = VaultWatcher(
            settings=s,
            chunker=mock_chunker,
            embedder=mock_embedder,
            store=mock_store,
            postgres_dsn="postgresql://test:test@localhost/test",
        )
        assert w._watch_config["watch_folders"] == []


# ---------------------------------------------------------------------------
# TestResolveCollectionAndType
# ---------------------------------------------------------------------------


class TestResolveCollectionAndType:
    def test_cac_concept_maps_to_cac_knowledge(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "cac" / "concepts" / "lcr.md")
        collection, doc_type, dept = watcher_with_config._resolve_collection_and_type(path)
        assert collection == "cac_knowledge"
        assert doc_type == "concept"
        assert dept == "CAC"

    def test_cac_decision_maps_correctly(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "cac" / "decisions" / "2026-01.md")
        collection, doc_type, dept = watcher_with_config._resolve_collection_and_type(path)
        assert collection == "cac_knowledge"
        assert doc_type == "decision_log"
        assert dept == "CAC"

    def test_shared_policy_maps_to_shared_policies(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "shared" / "policies" / "aml.md")
        collection, doc_type, dept = watcher_with_config._resolve_collection_and_type(path)
        assert collection == "shared_policies"
        assert doc_type == "policy_note"
        assert dept == "SHARED"

    def test_hr_concept_maps_to_hr_knowledge(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "hr" / "concepts" / "onboarding.md")
        collection, doc_type, dept = watcher_with_config._resolve_collection_and_type(path)
        assert collection == "hr_knowledge"
        assert doc_type == "concept"
        assert dept == "HR"

    def test_unmatched_path_falls_back(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "misc" / "random.md")
        collection, doc_type, dept = watcher_with_config._resolve_collection_and_type(path)
        assert collection == KNOWLEDGE_COLLECTION
        assert doc_type == "md"
        assert dept == "unknown"

    def test_path_outside_vault_falls_back(self, watcher_with_config: VaultWatcher) -> None:
        collection, doc_type, dept = watcher_with_config._resolve_collection_and_type(
            "/completely/different/path.md"
        )
        assert collection == KNOWLEDGE_COLLECTION
        assert dept == "unknown"

    def test_no_watch_config_falls_back(self, watcher: VaultWatcher) -> None:
        """Watcher with empty config always returns fallback values."""
        collection, doc_type, dept = watcher._resolve_collection_and_type(
            "/tmp/test-vault/cac/concepts/something.md"
        )
        assert collection == KNOWLEDGE_COLLECTION
        assert dept == "unknown"


# ---------------------------------------------------------------------------
# TestShouldIgnore
# ---------------------------------------------------------------------------


class TestShouldIgnore:
    def test_ignore_folder_at_root(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / ".obsidian" / "config.md")
        assert watcher_with_config._should_ignore(path) is True

    def test_ignore_nested_folder(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "cac" / "templates" / "meeting.md")
        assert watcher_with_config._should_ignore(path) is True

    def test_ignore_archive_folder(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "cac" / "archive" / "old.md")
        assert watcher_with_config._should_ignore(path) is True

    def test_ignore_listed_filename(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "cac" / "concepts" / "index.md")
        assert watcher_with_config._should_ignore(path) is True

    def test_ignore_log_md(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "shared" / "policies" / "log.md")
        assert watcher_with_config._should_ignore(path) is True

    def test_normal_file_not_ignored(self, watcher_with_config: VaultWatcher) -> None:
        vault = watcher_with_config._vault_path
        path = str(Path(vault) / "cac" / "concepts" / "lcr.md")
        assert watcher_with_config._should_ignore(path) is False

    def test_path_outside_vault_not_ignored(self, watcher_with_config: VaultWatcher) -> None:
        assert watcher_with_config._should_ignore("/other/path/note.md") is False

    def test_no_config_nothing_ignored(self, watcher: VaultWatcher) -> None:
        """Empty config means no file is ever ignored by config rules."""
        assert watcher._should_ignore("/tmp/test-vault/cac/concepts/note.md") is False


# ---------------------------------------------------------------------------
# TestProcessFile (updated for config-driven routing)
# ---------------------------------------------------------------------------


class TestProcessFile:
    async def test_new_file_ingested(
        self, watcher: VaultWatcher, mock_store: AsyncMock, tmp_path: Path
    ) -> None:
        """New file with no prior ingestion record gets chunked, embedded, and upserted."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\nSome content")

        already = patch.object(
            watcher, "_is_already_ingested", new_callable=AsyncMock, return_value=False
        )
        record = patch.object(watcher, "_record_ingestion", new_callable=AsyncMock)
        with already, record:
            await watcher._process_file(str(md_file))

        mock_store.delete_by_file.assert_called_once()
        mock_store.upsert_chunks.assert_called_once()

    async def test_unchanged_file_skipped(
        self, watcher: VaultWatcher, mock_store: AsyncMock, tmp_path: Path
    ) -> None:
        """File whose hash already matches ingested_documents is not re-processed."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\nSame content")

        already = patch.object(
            watcher, "_is_already_ingested", new_callable=AsyncMock, return_value=True
        )
        with already:
            await watcher._process_file(str(md_file))

        mock_store.upsert_chunks.assert_not_called()

    async def test_missing_file_skipped(
        self, watcher: VaultWatcher, mock_store: AsyncMock
    ) -> None:
        """Processing a path that no longer exists exits early without touching the store."""
        await watcher._process_file("/nonexistent/file.md")

        mock_store.delete_by_file.assert_not_called()
        mock_store.upsert_chunks.assert_not_called()

    async def test_empty_chunks_skipped(
        self,
        watcher: VaultWatcher,
        mock_chunker: AsyncMock,
        mock_store: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """File that produces no chunks does not call upsert."""
        md_file = tmp_path / "empty.md"
        md_file.write_text("")
        mock_chunker.chunk_file.return_value = []

        already = patch.object(
            watcher, "_is_already_ingested", new_callable=AsyncMock, return_value=False
        )
        record = patch.object(watcher, "_record_ingestion", new_callable=AsyncMock)
        with already, record:
            await watcher._process_file(str(md_file))

        mock_store.upsert_chunks.assert_not_called()

    async def test_record_ingestion_called_after_upsert(
        self, watcher: VaultWatcher, mock_store: AsyncMock, tmp_path: Path
    ) -> None:
        """Ingestion record is written to Postgres after successful upsert."""
        md_file = tmp_path / "note.md"
        md_file.write_text("# Meeting Notes\nDecision made.")

        already = patch.object(
            watcher, "_is_already_ingested", new_callable=AsyncMock, return_value=False
        )
        record = patch.object(watcher, "_record_ingestion", new_callable=AsyncMock)
        with already, record as mock_record:
            await watcher._process_file(str(md_file))

        mock_record.assert_called_once()
        call_args = mock_record.call_args
        assert call_args.args[0] == str(md_file)
        assert call_args.args[2] == 2  # two chunks from mock_chunker

    async def test_process_file_removes_from_pending(
        self, watcher: VaultWatcher, tmp_path: Path
    ) -> None:
        """_process_file pops its own key from _pending before processing."""
        md_file = tmp_path / "note.md"
        md_file.write_text("content")
        path_str = str(md_file)

        fake_handle = MagicMock()
        watcher._pending[path_str] = fake_handle

        already = patch.object(
            watcher, "_is_already_ingested", new_callable=AsyncMock, return_value=True
        )
        with already:
            await watcher._process_file(path_str)

        assert path_str not in watcher._pending

    async def test_config_driven_routing_uses_correct_collection(
        self,
        watcher_with_config: VaultWatcher,
        mock_store: AsyncMock,
        mock_chunker: AsyncMock,
    ) -> None:
        """Files in cac/concepts/ are upserted into cac_knowledge with doc_type=concept."""
        vault = Path(watcher_with_config._vault_path)
        vault.mkdir(parents=True, exist_ok=True)
        md_file = vault / "cac" / "concepts" / "lcr.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text("# LCR\nLiquidity coverage ratio.")

        already = patch.object(
            watcher_with_config, "_is_already_ingested", new_callable=AsyncMock, return_value=False
        )
        record = patch.object(watcher_with_config, "_record_ingestion", new_callable=AsyncMock)
        with already, record as mock_record:
            await watcher_with_config._process_file(str(md_file))

        upsert_call = mock_store.upsert_chunks.call_args
        assert upsert_call.kwargs["collection"] == "cac_knowledge"

        chunk_call = mock_chunker.chunk_file.call_args
        assert chunk_call.kwargs.get("doc_type") == "concept"
        assert chunk_call.kwargs.get("dept") == "CAC"

        # _record_ingestion receives the resolved dept and doc_type as kwargs
        rec_call = mock_record.call_args
        assert rec_call.kwargs.get("dept") == "CAC"
        assert rec_call.kwargs.get("doc_type") == "concept"

    async def test_shared_policy_routed_to_shared_policies_collection(
        self,
        watcher_with_config: VaultWatcher,
        mock_store: AsyncMock,
        mock_chunker: AsyncMock,
    ) -> None:
        """Files in shared/policies/ are upserted into shared_policies collection."""
        vault = Path(watcher_with_config._vault_path)
        md_file = vault / "shared" / "policies" / "aml.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text("# AML Policy")

        already = patch.object(
            watcher_with_config, "_is_already_ingested", new_callable=AsyncMock, return_value=False
        )
        record = patch.object(watcher_with_config, "_record_ingestion", new_callable=AsyncMock)
        with already, record:
            await watcher_with_config._process_file(str(md_file))

        upsert_call = mock_store.upsert_chunks.call_args
        assert upsert_call.kwargs["collection"] == "shared_policies"


# ---------------------------------------------------------------------------
# TestOnFileEvent (ignore-filter integration)
# ---------------------------------------------------------------------------


class TestOnFileEvent:
    def test_non_md_path_ignored(self, watcher: VaultWatcher) -> None:
        """_on_file_event ignores non-.md paths and adds nothing to _pending."""
        loop = asyncio.new_event_loop()
        watcher._loop = loop
        try:
            watcher._on_file_event("/vault/image.png")
            assert "/vault/image.png" not in watcher._pending
        finally:
            loop.close()

    def test_md_path_added_to_pending(self, watcher: VaultWatcher) -> None:
        """_on_file_event schedules a debounced task for .md paths."""
        loop = asyncio.new_event_loop()
        watcher._loop = loop
        try:
            watcher._on_file_event("/vault/note.md")
            assert "/vault/note.md" in watcher._pending
        finally:
            watcher._pending.get("/vault/note.md", MagicMock()).cancel()
            loop.close()

    def test_duplicate_event_cancels_previous_timer(self, watcher: VaultWatcher) -> None:
        """Second event for same file cancels the first debounce timer."""
        loop = asyncio.new_event_loop()
        watcher._loop = loop
        try:
            watcher._on_file_event("/vault/note.md")
            first_handle = watcher._pending["/vault/note.md"]
            watcher._on_file_event("/vault/note.md")
            second_handle = watcher._pending["/vault/note.md"]
            assert first_handle is not second_handle
        finally:
            watcher._pending.get("/vault/note.md", MagicMock()).cancel()
            loop.close()

    def test_no_loop_does_nothing(self, watcher: VaultWatcher) -> None:
        """_on_file_event with no running loop is a no-op."""
        watcher._loop = None
        watcher._on_file_event("/vault/note.md")
        assert watcher._pending == {}

    def test_ignored_file_not_added_to_pending(
        self, watcher_with_config: VaultWatcher
    ) -> None:
        """_on_file_event does not schedule processing for ignored paths."""
        vault = watcher_with_config._vault_path
        ignored_path = str(Path(vault) / ".obsidian" / "config.md")

        loop = asyncio.new_event_loop()
        watcher_with_config._loop = loop
        try:
            watcher_with_config._on_file_event(ignored_path)
            assert ignored_path not in watcher_with_config._pending
        finally:
            loop.close()

    def test_ignored_filename_not_added_to_pending(
        self, watcher_with_config: VaultWatcher
    ) -> None:
        """_on_file_event skips files listed in ignore_files."""
        vault = watcher_with_config._vault_path
        index_path = str(Path(vault) / "cac" / "concepts" / "index.md")

        loop = asyncio.new_event_loop()
        watcher_with_config._loop = loop
        try:
            watcher_with_config._on_file_event(index_path)
            assert index_path not in watcher_with_config._pending
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# TestVaultEventHandler
# ---------------------------------------------------------------------------


class TestVaultEventHandler:
    def test_md_file_triggers_callback_on_modified(self) -> None:
        """on_modified for a .md file calls the registered callback."""
        callback = MagicMock()
        handler = _VaultEventHandler(callback)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/vault/note.md"
        handler.on_modified(event)
        callback.assert_called_once_with("/vault/note.md")

    def test_md_file_triggers_callback_on_created(self) -> None:
        """on_created for a .md file calls the registered callback."""
        callback = MagicMock()
        handler = _VaultEventHandler(callback)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/vault/new_note.md"
        handler.on_created(event)
        callback.assert_called_once_with("/vault/new_note.md")

    def test_directory_modified_event_ignored(self) -> None:
        """on_modified for a directory does not call the callback."""
        callback = MagicMock()
        handler = _VaultEventHandler(callback)
        event = MagicMock()
        event.is_directory = True
        event.src_path = "/vault/subdir"
        handler.on_modified(event)
        callback.assert_not_called()

    def test_directory_created_event_ignored(self) -> None:
        """on_created for a directory does not call the callback."""
        callback = MagicMock()
        handler = _VaultEventHandler(callback)
        event = MagicMock()
        event.is_directory = True
        event.src_path = "/vault/subdir"
        handler.on_created(event)
        callback.assert_not_called()

    def test_non_md_file_still_forwarded(self) -> None:
        """Handler forwards all non-directory events; .md filtering is in _on_file_event."""
        callback = MagicMock()
        handler = _VaultEventHandler(callback)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/vault/image.png"
        handler.on_modified(event)
        # Handler always calls callback; VaultWatcher._on_file_event filters by .md
        callback.assert_called_once_with("/vault/image.png")


# ---------------------------------------------------------------------------
# TestStartStop
# ---------------------------------------------------------------------------


class TestStartStop:
    async def test_start_with_missing_vault_path(self, watcher: VaultWatcher) -> None:
        """start() with a non-existent vault path does not create an observer."""
        await watcher.start()
        assert watcher._observer is None

    async def test_stop_clears_observer_and_pending(self, watcher: VaultWatcher) -> None:
        """stop() ensures _observer is None and _pending is empty."""
        fake_handle = MagicMock()
        watcher._pending["/vault/note.md"] = fake_handle

        await watcher.stop()

        assert watcher._observer is None
        assert watcher._pending == {}
        fake_handle.cancel.assert_called_once()

    async def test_stop_without_observer_is_safe(self, watcher: VaultWatcher) -> None:
        """stop() is idempotent when observer was never started."""
        assert watcher._observer is None
        await watcher.stop()
        assert watcher._observer is None

    async def test_start_creates_observer_for_existing_path(
        self, watcher: VaultWatcher, tmp_path: Path
    ) -> None:
        """start() sets _observer and _loop when vault path exists."""
        watcher._vault_path = str(tmp_path)
        try:
            await watcher.start()
            assert watcher._observer is not None
            assert watcher._loop is not None
        finally:
            await watcher.stop()
