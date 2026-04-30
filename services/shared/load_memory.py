"""LangGraph node: load the agent memory triad (soul.md / user.md / memory.md)."""
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


def load_memory_node(state: dict) -> dict:
    """Read soul.md/user.md/memory.md for the active agent.

    Concatenates non-empty files into state['agent_memory'].
    Missing files are silently skipped.
    """
    vault_root = Path(state.get("vault_root", "/vault"))
    dept = state.get("dept_id", "unknown")
    agent = state.get("agent_id", "unknown")

    # Path traversal protection
    if not _SAFE_ID.match(dept) or not _SAFE_ID.match(agent):
        log.warning("Rejected unsafe dept_id=%s or agent_id=%s", dept, agent)
        return {"agent_memory": ""}

    base = vault_root / dept / "_memory" / agent

    parts = []
    for fname in ("soul.md", "user.md", "memory.md"):
        f = base / fname
        if f.is_file():
            content = f.read_text(encoding="utf-8").strip()
            if content:
                parts.append(content)

    return {"agent_memory": "\n\n---\n\n".join(parts)}
