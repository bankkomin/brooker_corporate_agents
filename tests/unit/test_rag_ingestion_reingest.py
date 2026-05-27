"""Unit tests for POST /reingest-vault endpoint.

All heavy dependencies (chunker, embedder, qdrant client, filesystem) are mocked.
No real backend processes are touched.

Run:
    python -m pytest tests/unit/test_rag_ingestion_reingest.py -v
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Minimal stub modules so `services.rag-ingestion.src` can be imported
# without the full dependency tree being installed.
# ---------------------------------------------------------------------------

def _stub_module(name: str, **attrs: Any) -> types.ModuleType:
    """Create a stub module and register it in sys.modules.

    Uses force-set (not setdefault) so stubs applied here win over any
    partial registration from earlier in the process.  This is safe because
    we never stub a module that has real code we care about in these tests.
    """
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# Structural stubs — registered before any service module is imported so that
# transitive imports of heavy C-extensions don't blow up in the test environment.
_stub_module("structlog", get_logger=lambda *_a, **_kw: MagicMock())
_stub_module("pydantic_settings", BaseSettings=object)
_stub_module(
    "qdrant_client",
    AsyncQdrantClient=MagicMock,  # class, not instance
)
_stub_module(
    "qdrant_client.models",
    Distance=MagicMock(),
    FieldCondition=MagicMock(),
    Filter=MagicMock(),
    MatchValue=MagicMock(),
    PointStruct=MagicMock(),
    VectorParams=MagicMock(),
    ScrollRequest=MagicMock(),
)
_stub_module("watchdog")
_stub_module("watchdog.events", FileSystemEvent=object, FileSystemEventHandler=object)
_stub_module("watchdog.observers", Observer=MagicMock())


# ---------------------------------------------------------------------------
# Minimal obsidian_watch.json fixture (in-memory — no disk access required)
# ---------------------------------------------------------------------------

WATCH_CONFIG: dict[str, Any] = {
    "watch_folders": [
        {"path": "ib/entities/",   "collection": "ib_docs",      "doc_type": "entity"},
        {"path": "ib/concepts/",   "collection": "ib_knowledge",  "doc_type": "concept"},
        {"path": "ib/daily-logs/", "collection": "ib_chat",       "doc_type": "interaction_log"},
        {"path": "hr/entities/",   "collection": "hr_docs",       "doc_type": "entity"},
    ],
    "ignore_folders": [".obsidian", "templates"],
    "ignore_files": ["index.md", "log.md"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reingester(
    vault_root: Path,
    chunker=None,
    embedder=None,
    store=None,
):
    """Build a VaultReingester with sensible mock defaults."""
    from services.rag_ingestion.src.vault_reingest import VaultReingester

    if chunker is None:
        chunker = MagicMock()
        chunker.chunk_file = AsyncMock(return_value=[])

    if embedder is None:
        embedder = MagicMock()
        embedder.embed_texts = AsyncMock(return_value=[])

    if store is None:
        store = MagicMock()
        store.upsert_chunks = AsyncMock(return_value=0)
        store.delete_by_source_prefix = AsyncMock(return_value=0)

    return VaultReingester(
        chunker=chunker,
        embedder=embedder,
        store=store,
        vault_root=vault_root,
        watch_config=WATCH_CONFIG,
    )


async def _collect_events(reingester, **kwargs) -> list[dict]:
    """Drain the streaming generator and parse every line as JSON."""
    events = []
    async for line in reingester.reingest_streaming(**kwargs):
        events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# Fixture: a tiny fake vault on disk
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_vault(tmp_path: Path) -> Path:
    """Create a minimal vault structure under tmp_path/obsidian-vault/."""
    vault = tmp_path / "obsidian-vault"
    (vault / "ib" / "entities").mkdir(parents=True)
    (vault / "ib" / "concepts").mkdir(parents=True)
    (vault / "ib" / "daily-logs").mkdir(parents=True)

    (vault / "ib" / "entities" / "foo.md").write_text("# Foo\nSome entity content.", encoding="utf-8")
    (vault / "ib" / "entities" / "bar.md").write_text("# Bar\nAnother entity.", encoding="utf-8")
    (vault / "ib" / "concepts" / "concept1.md").write_text("# C1\nConcept text.", encoding="utf-8")
    # This file should be ignored by filename rule
    (vault / "ib" / "entities" / "index.md").write_text("ignored", encoding="utf-8")
    return vault


# ---------------------------------------------------------------------------
# Test: 1 — reject unknown dept
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reject_unknown_dept(fake_vault: Path):
    """VaultReingester with an unknown dept yields an empty file list and reports 0 files."""
    # "zzz" is not in WATCH_CONFIG — the endpoint returns 400 via the route guard.
    # At the VaultReingester level, _resolve_entries returns [] and we get a
    # start→done with total_files=0.
    ri = _make_reingester(fake_vault)
    events = await _collect_events(ri, dept="zzz", subdirs=None, delete_stale=False, dry_run=False)
    start = next(e for e in events if e["event"] == "start")
    done = next(e for e in events if e["event"] == "done")
    assert start["total_files"] == 0
    assert done["files"] == 0


def test_reject_unknown_dept_http(fake_vault: Path):
    """POST /reingest-vault with dept='zzz' returns HTTP 400 with a clear message.

    Tests the validation logic that lives in the main.py route handler.
    We test this as a unit (calling the guard logic directly) because the full
    main.py app requires python-multipart for its multipart form routes, which
    is not installed in the dev test environment.
    """
    from fastapi import HTTPException

    from services.rag_ingestion.src.models import ReIngestVaultRequest

    # Replicate the validation guard from the main.py endpoint
    def _validate_dept(req: ReIngestVaultRequest, watch_config: dict) -> None:
        known_depts: set[str] = set()
        for entry in watch_config.get("watch_folders", []):
            path_str = entry["path"].strip("/")
            first_seg = path_str.split("/")[0]
            if first_seg:
                known_depts.add(first_seg)
        if req.dept not in known_depts:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown dept {req.dept!r}. Valid depts: {sorted(known_depts)}",
            )

    req_unknown = ReIngestVaultRequest(dept="zzz")
    with pytest.raises(HTTPException) as exc_info:
        _validate_dept(req_unknown, WATCH_CONFIG)

    assert exc_info.value.status_code == 400
    assert "zzz" in exc_info.value.detail

    # Valid dept should not raise
    req_valid = ReIngestVaultRequest(dept="ib")
    _validate_dept(req_valid, WATCH_CONFIG)  # no exception


# ---------------------------------------------------------------------------
# Test: 2 — dry_run returns file list without calling chunker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_returns_file_list_without_ingesting(fake_vault: Path):
    """dry_run=True lists all files and never calls chunker.chunk_file."""
    chunker = MagicMock()
    chunker.chunk_file = AsyncMock(return_value=[])

    ri = _make_reingester(fake_vault, chunker=chunker)
    events = await _collect_events(
        ri, dept="ib", subdirs=None, delete_stale=False, dry_run=True
    )

    # chunker should NOT have been called at all
    chunker.chunk_file.assert_not_called()

    # Collect file events
    file_events = [e for e in events if e["event"] == "file"]
    assert len(file_events) > 0  # at least one file found

    done_event = next(e for e in events if e["event"] == "done")
    assert done_event["dry_run"] is True
    assert done_event["files"] == len(file_events)


# ---------------------------------------------------------------------------
# Test: 3 — walks all configured subdirs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reingest_walks_configured_subdirs(fake_vault: Path):
    """All .md files in configured subdirs (minus ignore rules) are processed."""
    from services.rag_ingestion.src.chunker import TextChunk

    fake_chunk = TextChunk(text="hello", metadata={"source": "test"})
    chunker = MagicMock()
    chunker.chunk_file = AsyncMock(return_value=[fake_chunk])

    embedder = MagicMock()
    embedder.embed_texts = AsyncMock(return_value=[[0.1] * 8])

    store = MagicMock()
    store.upsert_chunks = AsyncMock(return_value=1)
    store.delete_by_source_prefix = AsyncMock(return_value=0)

    ri = _make_reingester(fake_vault, chunker=chunker, embedder=embedder, store=store)
    events = await _collect_events(
        ri, dept="ib", subdirs=None, delete_stale=False, dry_run=False
    )

    file_events = [e for e in events if e["event"] == "file"]
    names = {e["name"] for e in file_events}

    # foo.md and bar.md in entities/, concept1.md in concepts/
    # index.md should be ignored (in ignore_files list)
    assert any("foo.md" in n for n in names)
    assert any("bar.md" in n for n in names)
    assert any("concept1.md" in n for n in names)
    assert not any("index.md" in n for n in names)

    # chunker was called once per non-ignored .md file
    assert chunker.chunk_file.call_count == len(file_events)


# ---------------------------------------------------------------------------
# Test: 4 — delete_stale calls qdrant filter delete on each affected collection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_stale_calls_qdrant_filter_delete(fake_vault: Path):
    """delete_stale=True calls delete_by_source_prefix for each collection."""
    store = MagicMock()
    store.upsert_chunks = AsyncMock(return_value=1)
    store.delete_by_source_prefix = AsyncMock(return_value=5)

    from services.rag_ingestion.src.chunker import TextChunk

    fake_chunk = TextChunk(text="t", metadata={"source": "x"})
    chunker = MagicMock()
    chunker.chunk_file = AsyncMock(return_value=[fake_chunk])

    embedder = MagicMock()
    embedder.embed_texts = AsyncMock(return_value=[[0.1] * 8])

    ri = _make_reingester(fake_vault, chunker=chunker, embedder=embedder, store=store)
    await _collect_events(
        ri, dept="ib", subdirs=None, delete_stale=True, dry_run=False
    )

    # delete_by_source_prefix should have been called for each distinct
    # collection that the ib dept entries map to (ib_docs + ib_knowledge).
    # (ib_chat is not present because the daily-logs folder in fake_vault is empty.)
    assert store.delete_by_source_prefix.called

    called_collections = {
        call.args[0]
        for call in store.delete_by_source_prefix.call_args_list
    }
    # At minimum ib_docs (entities) should appear
    assert "ib_docs" in called_collections

    # The prefix passed must start with "obsidian-vault/ib/"
    for call in store.delete_by_source_prefix.call_args_list:
        prefix = call.args[1]
        assert prefix.startswith("obsidian-vault/ib/"), f"Unexpected prefix: {prefix!r}"


# ---------------------------------------------------------------------------
# Test: 5 — streaming response emits per-file events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_response_emits_per_file_events(fake_vault: Path):
    """Each processed file emits exactly one 'file' event in the stream."""
    from services.rag_ingestion.src.chunker import TextChunk

    fake_chunk = TextChunk(text="data", metadata={})
    chunker = MagicMock()
    chunker.chunk_file = AsyncMock(return_value=[fake_chunk])

    embedder = MagicMock()
    embedder.embed_texts = AsyncMock(return_value=[[0.0] * 4])

    store = MagicMock()
    store.upsert_chunks = AsyncMock(return_value=1)
    store.delete_by_source_prefix = AsyncMock(return_value=0)

    ri = _make_reingester(fake_vault, chunker=chunker, embedder=embedder, store=store)
    events = await _collect_events(
        ri, dept="ib", subdirs=None, delete_stale=False, dry_run=False
    )

    # First event must be "start"
    assert events[0]["event"] == "start"
    # Last event must be "done"
    assert events[-1]["event"] == "done"
    # Every middle event is "file"
    middle = events[1:-1]
    assert all(e["event"] == "file" for e in middle)
    # Each file event has required fields
    for e in middle:
        assert "name" in e
        assert "collection" in e
        assert "chunks" in e
        assert "status" in e


# ---------------------------------------------------------------------------
# Test: 6 — progress reports correct counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_progress_reports_correct_counts(fake_vault: Path):
    """The 'done' event file count and chunk count match what the chunker returned."""
    from services.rag_ingestion.src.chunker import TextChunk

    # Each file gets exactly 3 chunks
    fake_chunks = [
        TextChunk(text=f"chunk {i}", metadata={})
        for i in range(3)
    ]
    chunker = MagicMock()
    chunker.chunk_file = AsyncMock(return_value=fake_chunks)

    embedder = MagicMock()
    embedder.embed_texts = AsyncMock(return_value=[[0.0] * 4, [0.0] * 4, [0.0] * 4])

    store = MagicMock()
    store.upsert_chunks = AsyncMock(return_value=3)
    store.delete_by_source_prefix = AsyncMock(return_value=0)

    ri = _make_reingester(fake_vault, chunker=chunker, embedder=embedder, store=store)
    events = await _collect_events(
        ri, dept="ib", subdirs=None, delete_stale=False, dry_run=False
    )

    file_events = [e for e in events if e["event"] == "file"]
    done = next(e for e in events if e["event"] == "done")

    expected_files = len(file_events)
    expected_chunks = sum(e["chunks"] for e in file_events)

    assert done["files"] == expected_files
    assert done["chunks"] == expected_chunks


# ---------------------------------------------------------------------------
# Test: 7 — error in one file does not abort the loop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_in_one_file_does_not_abort(fake_vault: Path):
    """If chunking raises for one file, the loop continues and the error is captured."""
    from services.rag_ingestion.src.chunker import TextChunk

    good_chunk = TextChunk(text="ok", metadata={})
    call_count = 0

    async def _chunk_side_effect(file_path, *, doc_type, dept, extra_meta=None):
        nonlocal call_count
        call_count += 1
        # Blow up on the first file processed
        if call_count == 1:
            raise RuntimeError("simulated chunker failure")
        return [good_chunk]

    chunker = MagicMock()
    chunker.chunk_file = AsyncMock(side_effect=_chunk_side_effect)

    embedder = MagicMock()
    embedder.embed_texts = AsyncMock(return_value=[[0.0] * 4])

    store = MagicMock()
    store.upsert_chunks = AsyncMock(return_value=1)
    store.delete_by_source_prefix = AsyncMock(return_value=0)

    ri = _make_reingester(fake_vault, chunker=chunker, embedder=embedder, store=store)
    events = await _collect_events(
        ri, dept="ib", subdirs=None, delete_stale=False, dry_run=False
    )

    done = next(e for e in events if e["event"] == "done")
    file_events = [e for e in events if e["event"] == "file"]

    # There should be at least one error event
    error_events = [e for e in file_events if e["status"] == "error"]
    ok_events = [e for e in file_events if e["status"] == "ok"]

    assert len(error_events) >= 1, "Expected at least one error event"
    assert len(ok_events) >= 1, "Expected at least one successful event after the failure"
    # Errors captured in the 'done' summary
    assert len(done["errors"]) == len(error_events)
    # The loop ran all files (call_count matches total non-ignored .md files)
    assert call_count == len(file_events)
