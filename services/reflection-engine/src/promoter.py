import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_SAFE_SECTION = re.compile(r"^[a-zA-Z0-9 _-]+$")
_HTML_TAG = re.compile(r"<[^>]+>")

# Bound memory.md growth: the reflection LLM is forced into these three fixed
# sections (it used to invent a new section name each night, so memory.md grew
# without limit). Each section is also size-capped.
_MEMORY_SECTIONS = ["Lessons", "Patterns", "Known Gaps"]
_MAX_SECTION_CHARS = 1500
_MAX_USER_SECTIONS = 25


def _normalize_memory_section(name: str) -> str:
    """Collapse any LLM section name into one of the three fixed buckets."""
    n = (name or "").lower()
    if "pattern" in n:
        return "Patterns"
    if "gap" in n or "missing" in n or "unknown" in n or "todo" in n:
        return "Known Gaps"
    return "Lessons"


def _sanitize_section(name: str) -> str:
    """Validate section name is safe for markdown heading."""
    clean = name.strip()
    if not _SAFE_SECTION.match(clean):
        log.warning("Rejected unsafe section name: %s", clean)
        return "General"
    return clean


def _sanitize_content(content: str) -> str:
    """Strip HTML tags and dangerous patterns from LLM output."""
    cleaned = _HTML_TAG.sub("", content)
    # Block common prompt injection patterns
    for pattern in ["ignore previous", "system prompt", "<script", "javascript:"]:
        if pattern.lower() in cleaned.lower():
            log.warning("Blocked suspicious content pattern: %s", pattern)
            cleaned = cleaned.replace(pattern, "[REDACTED]")
    return cleaned


def promote_memory(mem_dir: Path, sdk_output: dict) -> dict:
    """Apply reflection output to memory.md and user.md files.

    Archives existing files before overwriting.
    Returns summary of changes made.
    """
    changes = {"memory_updated": False, "user_updated": False, "archived": []}

    # Archive + update memory.md — collapsed into 3 fixed, size-capped sections.
    memory_updates = sdk_output.get("memory_md_updates", [])
    if memory_updates:
        memory_file = mem_dir / "memory.md"
        _archive_file(memory_file, mem_dir, changes)
        _apply_updates(memory_file, memory_updates,
                       normalize=_normalize_memory_section, fixed=_MEMORY_SECTIONS)
        changes["memory_updated"] = True

    # Archive + update user.md — sections are per-user; cap the count.
    user_updates = sdk_output.get("user_md_updates", [])
    if user_updates:
        user_file = mem_dir / "user.md"
        _archive_file(user_file, mem_dir, changes)
        _apply_updates(user_file, user_updates, max_sections=_MAX_USER_SECTIONS)
        changes["user_updated"] = True

    return changes


def _archive_file(file_path: Path, mem_dir: Path, changes: dict):
    """Copy existing file to history/ with date suffix before overwriting."""
    if not file_path.exists():
        return

    history_dir = mem_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    archive_name = f"{date_str}-{file_path.name}"
    archive_path = history_dir / archive_name

    # Don't overwrite same-day archive
    if not archive_path.exists():
        shutil.copy2(file_path, archive_path)
        changes["archived"].append(str(archive_path))
        log.info("Archived %s → %s", file_path.name, archive_path)


def _apply_updates(file_path: Path, updates: list[dict], *, normalize=None,
                   fixed: list[str] | None = None, max_sections: int | None = None):
    """Write section-based updates to a markdown file, bounding growth.

    - normalize: optional fn mapping an LLM section name to a canonical bucket.
    - fixed: if set, only these section names survive (in this order) — prevents
      unbounded section accumulation.
    - max_sections: if set, keep only the most-recent N sections.
    Section content is always truncated to _MAX_SECTION_CHARS.
    """
    existing_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    sections = _parse_sections(existing_content)

    for update in updates:
        section = update.get("section", "General")
        if normalize is not None:
            section = normalize(section)
        section = _sanitize_section(section)
        content = _sanitize_content(update.get("content", ""))[:_MAX_SECTION_CHARS]
        sections[section] = content

    if fixed is not None:
        sections = {k: sections[k] for k in fixed if k in sections}
    elif max_sections is not None and len(sections) > max_sections:
        keep = list(sections)[-max_sections:]
        sections = {k: sections[k] for k in keep}

    lines = []
    for section_name, section_content in sections.items():
        lines.append(f"## {section_name}\n")
        lines.append(section_content.strip())
        lines.append("")

    file_path.write_text("\n".join(lines), encoding="utf-8")


def _parse_sections(text: str) -> dict[str, str]:
    """Parse markdown into {section_name: content} dict."""
    sections: dict[str, str] = {}
    current_section = "General"
    current_lines: list[str] = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_lines:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections
