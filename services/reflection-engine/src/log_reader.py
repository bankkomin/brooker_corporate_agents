"""Parse daily-log markdown files written by services/shared/daily_log.py.

Supports two header variants:
  - Standard:  ## HH:MM · @USER · proposal: PROP_ID
  - Legacy:    ## HH:MM · @USER · proposal: PROP_ID   (same)

Field variants tolerated:
  - Confidence: 0.91   (standard)
  - Latency: 1234ms    (CEO orchestrator emits latency, not confidence)
"""
from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from pathlib import Path

_HEADER_RE = re.compile(
    r"(\d{2}:\d{2})\s*[·•]\s*@(\S+)\s*[·•]\s*proposal:\s*(\S+)"
)
_FIELD_RE = re.compile(r"\*\*([^:*]+):\*\*\s*(.*)")
_LATENCY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


@dataclass
class LogEntry:
    timestamp: str = ""
    user_id: str = ""
    proposal_id: str | None = None
    query: str = ""
    response: str = ""
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    outcome: str = "pending"


def parse_daily_log(path: Path) -> list[LogEntry]:
    """Parse a daily-log markdown file into structured LogEntry objects.

    Returns an empty list if the file is missing or empty.
    Never raises — malformed blocks are silently skipped.
    """
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    # Split on section headers (## at start of line or after newline)
    blocks = re.split(r"\n## ", "\n" + text)
    entries: list[LogEntry] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        header_match = _HEADER_RE.search(block)
        if not header_match:
            continue

        raw_proposal = header_match.group(3)
        entry = LogEntry(
            timestamp=header_match.group(1),
            user_id=header_match.group(2),
            proposal_id=raw_proposal if raw_proposal.lower() != "none" else None,
        )

        for field_match in _FIELD_RE.finditer(block):
            key = field_match.group(1).strip().lower()
            val = field_match.group(2).strip()

            if key in ("q", "query"):
                entry.query = val
            elif key in ("a", "answer", "response"):
                entry.response = val
            elif key == "citations":
                entry.citations = [c.strip() for c in val.split(",") if c.strip()]
            elif key == "confidence":
                with contextlib.suppress(ValueError):
                    entry.confidence = float(val)
            elif key == "latency":
                # CEO orchestrator emits "Latency: 1234ms" — convert to rough signal
                lat_match = _LATENCY_RE.search(val)
                if lat_match:
                    # Not a real confidence; leave at 0 so memory promoter sees no signal
                    pass
            elif key == "outcome":
                entry.outcome = val

        entries.append(entry)

    return entries
