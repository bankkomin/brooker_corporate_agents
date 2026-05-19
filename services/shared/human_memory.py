"""Human-curated memory management — replaces LLM-generated reflection with direct human input."""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass
class MemoryEntry:
    section: str
    content: str
    author: str
    pinned: bool = False  # pinned entries don't auto-expire
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None  # auto-archive after this date


@dataclass
class MemoryState:
    dept_id: str
    agent_id: str
    soul: str  # read-only, admin-authored
    user_entries: list[MemoryEntry] = field(default_factory=list)
    memory_entries: list[MemoryEntry] = field(default_factory=list)


def get_memory(dept_id: str, agent_id: str, vault_root: str = "/vault") -> MemoryState:
    """Read current memory state for an agent."""
    if not _SAFE_ID.match(dept_id) or not _SAFE_ID.match(agent_id):
        return MemoryState(dept_id=dept_id, agent_id=agent_id, soul="")

    base = Path(vault_root) / dept_id / "_memory" / agent_id

    soul = ""
    soul_path = base / "soul.md"
    if soul_path.exists():
        soul = soul_path.read_text(encoding="utf-8")

    return MemoryState(
        dept_id=dept_id,
        agent_id=agent_id,
        soul=soul,
        user_entries=_parse_entries(base / "user.md"),
        memory_entries=_parse_entries(base / "memory.md"),
    )


def add_memory_entry(
    dept_id: str,
    agent_id: str,
    file_type: str,  # "memory" or "user"
    entry: MemoryEntry,
    vault_root: str = "/vault",
) -> bool:
    """Add a human-authored entry to memory.md or user.md."""
    if not _SAFE_ID.match(dept_id) or not _SAFE_ID.match(agent_id):
        return False
    if file_type not in ("memory", "user"):
        return False

    base = Path(vault_root) / dept_id / "_memory" / agent_id
    base.mkdir(parents=True, exist_ok=True)
    file_path = base / f"{file_type}.md"

    # Archive before modifying
    _archive(file_path, base)

    # Read existing content
    existing = file_path.read_text(encoding="utf-8") if file_path.exists() else ""

    # Append new entry
    pin_marker = " [PINNED]" if entry.pinned else ""
    new_block = (
        f"\n## {entry.section}{pin_marker}\n"
        f"*Added by {entry.author} on {entry.created_at.strftime('%Y-%m-%d')}*\n\n"
        f"{entry.content}\n"
    )

    file_path.write_text(existing + new_block, encoding="utf-8")
    log.info(
        "Memory entry added: %s/%s/%s.md section=%s by=%s",
        dept_id, agent_id, file_type, entry.section, entry.author,
    )
    return True


def remove_memory_section(
    dept_id: str,
    agent_id: str,
    file_type: str,
    section_name: str,
    vault_root: str = "/vault",
) -> bool:
    """Remove a section from memory.md or user.md."""
    if not _SAFE_ID.match(dept_id) or not _SAFE_ID.match(agent_id):
        return False

    base = Path(vault_root) / dept_id / "_memory" / agent_id
    file_path = base / f"{file_type}.md"

    if not file_path.exists():
        return False

    _archive(file_path, base)

    content = file_path.read_text(encoding="utf-8")
    sections = _split_sections(content)

    if section_name not in sections:
        return False

    del sections[section_name]

    # Rebuild
    rebuilt = "\n".join(f"## {name}\n{body}\n" for name, body in sections.items())
    file_path.write_text(rebuilt, encoding="utf-8")
    return True


def prune_expired(dept_id: str, agent_id: str, vault_root: str = "/vault") -> int:
    """Remove expired (non-pinned) entries older than 90 days. Returns count removed."""
    base = Path(vault_root) / dept_id / "_memory" / agent_id
    removed = 0

    for file_type in ("memory", "user"):
        file_path = base / f"{file_type}.md"
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")
        sections = _split_sections(content)
        to_remove = []

        for name, body in sections.items():
            if "[PINNED]" in name:
                continue
            # Check if older than 90 days
            date_match = re.search(r"on (\d{4}-\d{2}-\d{2})", body)
            if date_match:
                entry_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                if (datetime.utcnow() - entry_date).days > 90:
                    to_remove.append(name)

        if to_remove:
            _archive(file_path, base)
            for name in to_remove:
                del sections[name]
            rebuilt = "\n".join(f"## {name}\n{body}\n" for name, body in sections.items())
            file_path.write_text(rebuilt, encoding="utf-8")
            removed += len(to_remove)

    return removed


def _parse_entries(file_path: Path) -> list[MemoryEntry]:
    if not file_path.exists():
        return []
    sections = _split_sections(file_path.read_text(encoding="utf-8"))
    entries = []
    for name, body in sections.items():
        pinned = "[PINNED]" in name
        clean_name = name.replace(" [PINNED]", "").strip()
        author = "unknown"
        author_match = re.search(r"Added by (\S+)", body)
        if author_match:
            author = author_match.group(1)
        entries.append(MemoryEntry(section=clean_name, content=body.strip(), author=author, pinned=pinned))
    return entries


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = "General"
    lines: list[str] = []
    for line in text.split("\n"):
        if line.startswith("## "):
            content = "\n".join(lines).strip()
            if content:
                sections[current] = content
            current = line[3:].strip()
            lines = []
        else:
            lines.append(line)
    content = "\n".join(lines).strip()
    if content:
        sections[current] = content
    return sections


def _archive(file_path: Path, base: Path) -> None:
    if not file_path.exists():
        return
    import shutil

    history = base / "history"
    history.mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y-%m-%d-%H%M")
    dest = history / f"{date_str}-{file_path.name}"
    if not dest.exists():
        shutil.copy2(file_path, dest)
