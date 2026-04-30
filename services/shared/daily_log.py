"""Daily interaction log writer for Obsidian vault."""
import logging
import re
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


def log_interaction_node(state: dict) -> dict:
    """LangGraph node: append interaction to daily-logs/YYYY-MM-DD.md.

    Expected state keys: vault_root, dept_id, user_id, query, response,
    citations (list), confidence (float), proposal_id (optional).
    """
    vault = Path(state.get("vault_root", "/vault"))
    dept = state["dept_id"]

    # Path traversal protection
    if not _SAFE_ID.match(dept):
        log.warning("Rejected unsafe dept_id: %s", dept)
        return state

    log_dir = vault / dept / "daily-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    f = log_dir / f"{today}.md"

    citations = state.get("citations", [])
    citations_str = ", ".join(citations) if citations else ""
    proposal_id = state.get("proposal_id", "none")

    entry = (
        f"\n## {now.strftime('%H:%M')} · @{state.get('user_id', '?')} · proposal: {proposal_id}\n"
        f"**Q:** {state.get('query', '')}\n"
        f"**A:** {state.get('response', '')}\n"
        f"**Citations:** {citations_str}\n"
        f"**Confidence:** {state.get('confidence', 0.0):.2f}\n"
        f"**Outcome:** pending\n"
    )

    with f.open("a", encoding="utf-8") as fp:
        fp.write(entry)

    return state
