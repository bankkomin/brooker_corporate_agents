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

    # Audit bug #8: state keys for cac/hr orchestrators are
    # `sources` (not `citations`), `answer` (not `response`),
    # `staging_proposal_id` (not `proposal_id`). Accept either set.
    citations_raw = state.get("citations") or state.get("sources") or []
    citation_strs: list[str] = []
    for c in citations_raw:
        if isinstance(c, str):
            citation_strs.append(c)
        elif isinstance(c, dict):
            citation_strs.append(
                c.get("filename")
                or c.get("source")
                or c.get("type")
                or "src"
            )
    citations_str = ", ".join(citation_strs)
    proposal_id = (
        state.get("proposal_id")
        or state.get("staging_proposal_id")
        or "none"
    )
    response_text = state.get("response") or state.get("answer") or ""

    confidence = state.get("confidence", 0.0)
    if isinstance(confidence, (int, float)):
        confidence_str = f"{confidence:.2f}"
    else:
        confidence_str = str(confidence)

    entry = (
        f"\n## {now.strftime('%H:%M')} · @{state.get('user_id', '?')} · proposal: {proposal_id}\n"
        f"**Q:** {state.get('query', '')}\n"
        f"**A:** {response_text}\n"
        f"**Citations:** {citations_str}\n"
        f"**Confidence:** {confidence_str}\n"
        f"**Outcome:** pending\n"
    )

    with f.open("a", encoding="utf-8") as fp:
        fp.write(entry)

    return state
