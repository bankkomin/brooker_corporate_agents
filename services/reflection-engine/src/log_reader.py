import re
from dataclasses import dataclass, field
from pathlib import Path


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


HEADER_RE = re.compile(
    r"(\d{2}:\d{2})\s*·\s*@(\S+)\s*·\s*proposal:\s*(\S+)"
)
FIELD_RE = re.compile(r"\*\*(\w+):\*\*\s*(.*)")


def parse_daily_log(path: Path) -> list[LogEntry]:
    """Parse a daily-log markdown file into structured entries."""
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n## ", text)
    entries = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        header_match = HEADER_RE.search(block)
        if not header_match:
            continue

        entry = LogEntry(
            timestamp=header_match.group(1),
            user_id=header_match.group(2),
            proposal_id=header_match.group(3) if header_match.group(3) != "none" else None,
        )

        for field_match in FIELD_RE.finditer(block):
            key = field_match.group(1).lower()
            val = field_match.group(2).strip()
            if key == "q":
                entry.query = val
            elif key == "a":
                entry.response = val
            elif key == "citations":
                entry.citations = [c.strip() for c in val.split(",") if c.strip()]
            elif key == "confidence":
                try:
                    entry.confidence = float(val)
                except ValueError:
                    pass
            elif key == "outcome":
                entry.outcome = val

        entries.append(entry)

    return entries
