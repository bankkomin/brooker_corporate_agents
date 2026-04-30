"""Tests for services.shared.human_memory — Phase 5.2 human-curated memory."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from services.shared.human_memory import (
    MemoryEntry,
    add_memory_entry,
    get_memory,
    prune_expired,
    remove_memory_section,
)


@pytest.fixture()
def vault(tmp_path):
    """Create a minimal vault directory structure."""
    base = tmp_path / "cac" / "_memory" / "liquidity-agent"
    base.mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def vault_with_soul(vault):
    """Vault that already has a soul.md file."""
    soul_path = vault / "cac" / "_memory" / "liquidity-agent" / "soul.md"
    soul_path.write_text("You are the liquidity agent.", encoding="utf-8")
    return vault


# --- get_memory ---


def test_get_memory_empty(vault):
    state = get_memory("cac", "liquidity-agent", vault_root=str(vault))
    assert state.dept_id == "cac"
    assert state.agent_id == "liquidity-agent"
    assert state.soul == ""
    assert state.user_entries == []
    assert state.memory_entries == []


def test_get_memory_with_soul(vault_with_soul):
    state = get_memory("cac", "liquidity-agent", vault_root=str(vault_with_soul))
    assert state.soul == "You are the liquidity agent."


def test_get_memory_invalid_ids():
    state = get_memory("../../etc", "passwd", vault_root="/tmp")
    assert state.soul == ""
    assert state.user_entries == []


def test_get_memory_reads_entries(vault):
    base = vault / "cac" / "_memory" / "liquidity-agent"
    (base / "user.md").write_text(
        "## Preferences\n*Added by alice on 2026-04-01*\n\nUse formal tone.\n",
        encoding="utf-8",
    )
    state = get_memory("cac", "liquidity-agent", vault_root=str(vault))
    assert len(state.user_entries) == 1
    assert state.user_entries[0].section == "Preferences"
    assert state.user_entries[0].author == "alice"


# --- add_memory_entry ---


def test_add_memory_entry(vault):
    entry = MemoryEntry(section="Context", content="Q2 focus on FX risk.", author="bob")
    result = add_memory_entry("cac", "liquidity-agent", "memory", entry, vault_root=str(vault))
    assert result is True

    state = get_memory("cac", "liquidity-agent", vault_root=str(vault))
    assert len(state.memory_entries) == 1
    assert state.memory_entries[0].section == "Context"


def test_add_memory_entry_pinned(vault):
    entry = MemoryEntry(section="Critical", content="Always escalate.", author="ceo", pinned=True)
    add_memory_entry("cac", "liquidity-agent", "user", entry, vault_root=str(vault))

    state = get_memory("cac", "liquidity-agent", vault_root=str(vault))
    assert len(state.user_entries) == 1
    assert state.user_entries[0].pinned is True


def test_add_memory_entry_invalid_file_type(vault):
    entry = MemoryEntry(section="X", content="Y", author="z")
    assert add_memory_entry("cac", "liquidity-agent", "soul", entry, vault_root=str(vault)) is False


def test_add_memory_entry_invalid_ids(vault):
    entry = MemoryEntry(section="X", content="Y", author="z")
    assert add_memory_entry("../bad", "agent", "memory", entry, vault_root=str(vault)) is False


def test_add_memory_creates_archive(vault):
    entry1 = MemoryEntry(section="First", content="Hello.", author="alice")
    add_memory_entry("cac", "liquidity-agent", "memory", entry1, vault_root=str(vault))

    entry2 = MemoryEntry(section="Second", content="World.", author="bob")
    add_memory_entry("cac", "liquidity-agent", "memory", entry2, vault_root=str(vault))

    history = vault / "cac" / "_memory" / "liquidity-agent" / "history"
    assert history.exists()
    assert len(list(history.iterdir())) >= 1


# --- remove_memory_section ---


def test_remove_memory_section(vault):
    entry = MemoryEntry(section="Temporary", content="Remove me.", author="alice")
    add_memory_entry("cac", "liquidity-agent", "memory", entry, vault_root=str(vault))

    result = remove_memory_section("cac", "liquidity-agent", "memory", "Temporary", vault_root=str(vault))
    assert result is True

    state = get_memory("cac", "liquidity-agent", vault_root=str(vault))
    assert all(e.section != "Temporary" for e in state.memory_entries)


def test_remove_memory_section_not_found(vault):
    entry = MemoryEntry(section="Keep", content="Stay.", author="alice")
    add_memory_entry("cac", "liquidity-agent", "memory", entry, vault_root=str(vault))

    result = remove_memory_section("cac", "liquidity-agent", "memory", "NonExistent", vault_root=str(vault))
    assert result is False


def test_remove_memory_section_no_file(vault):
    result = remove_memory_section("cac", "liquidity-agent", "memory", "Any", vault_root=str(vault))
    assert result is False


# --- prune_expired ---


def test_prune_expired_removes_old_entries(vault):
    base = vault / "cac" / "_memory" / "liquidity-agent"
    old_date = (datetime.utcnow() - timedelta(days=100)).strftime("%Y-%m-%d")
    (base / "memory.md").write_text(
        f"## Old Entry\n*Added by alice on {old_date}*\n\nStale data.\n",
        encoding="utf-8",
    )

    removed = prune_expired("cac", "liquidity-agent", vault_root=str(vault))
    assert removed == 1

    state = get_memory("cac", "liquidity-agent", vault_root=str(vault))
    assert len(state.memory_entries) == 0


def test_prune_expired_keeps_pinned(vault):
    base = vault / "cac" / "_memory" / "liquidity-agent"
    old_date = (datetime.utcnow() - timedelta(days=100)).strftime("%Y-%m-%d")
    (base / "memory.md").write_text(
        f"## Important [PINNED]\n*Added by ceo on {old_date}*\n\nNever remove.\n",
        encoding="utf-8",
    )

    removed = prune_expired("cac", "liquidity-agent", vault_root=str(vault))
    assert removed == 0


def test_prune_expired_keeps_recent(vault):
    base = vault / "cac" / "_memory" / "liquidity-agent"
    recent_date = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")
    (base / "memory.md").write_text(
        f"## Recent\n*Added by alice on {recent_date}*\n\nFresh.\n",
        encoding="utf-8",
    )

    removed = prune_expired("cac", "liquidity-agent", vault_root=str(vault))
    assert removed == 0
