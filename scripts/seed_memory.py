"""Seed the agent memory triad (soul.md / memory.md / user.md) for every
department agent, so the reflection-engine learning loop goes from dormant to
active. soul.md is derived from each agent's grounded SKILL.md mandate. memory.md
is initialised with the three fixed sections the promoter maintains; user.md
starts empty. Existing memory.md / user.md are NOT overwritten (only soul.md is
refreshed) so a re-run never destroys accumulated learning.
"""
from __future__ import annotations

import re
from pathlib import Path

VAULT = Path("obsidian-vault")

# dept -> (skill file, agent-dir name == runtime agent_id)
AGENTS = {
    "cac":     ("skills/cac/cac-agent.md",      "cac-agent"),
    "ceo":     ("skills/ceo/ceo-agent.md",      "ceo-agent"),
    "cio":     ("skills/cio/cio-agent.md",      "cio-agent"),
    "vcc":     ("skills/vcc/vcc-agent.md",      "vcc-agent"),
    "comms":   ("skills/comms/comms-agent.md",  "comms-agent"),
    "finance": ("skills/finance/cfo-agent.md",  "cfo-agent"),
    "ib":      ("skills/ib/ib-agent.md",        "ib-agent"),
    "ic":      ("skills/ic/ic-agent.md",        "ic-agent"),
    "it":      ("skills/it/it-agent.md",        "it-agent"),
    "legal":   ("skills/legal/legal-agent.md",  "legal-agent"),
    "risk":    ("skills/risk/risk-agent.md",    "risk-agent"),
    "hr":      ("skills/hr/hr-agent.md",        "hr-agent"),
}


def _extract_mandate(skill_text: str) -> str:
    """Pull the text under the '## Mandate' heading (until the next heading)."""
    m = re.search(r"##\s*Mandate\s*\n(.+?)(?:\n##\s|\Z)", skill_text, re.DOTALL)
    return m.group(1).strip() if m else "(mandate not found in skill file)"


def _soul(dept: str, agent: str, mandate: str) -> str:
    return f"""# Soul — {agent}

I am the **{agent}** for the Brooker Group **{dept.upper()}** department.

## Mandate
{mandate}

## How I work
- Answer ONLY from retrieved department documents + my skill; cite sources.
- If I have no grounded source, I abstain and flag the HOD — I never fabricate
  figures, names, or thresholds.
- I propose changes to the human approval gate (staging); I never write live data.
- I carry forward the lessons in `memory.md` and the user notes in `user.md`.
"""


_MEMORY_INIT = """## Lessons
(none yet — populated nightly by the reflection engine)

## Patterns
(none yet)

## Known Gaps
(none yet)
"""

_USER_INIT = "# Users\n(no per-user notes yet)\n"


def main() -> int:
    seeded = 0
    for dept, (skill_path, agent) in AGENTS.items():
        sp = Path(skill_path)
        if not sp.exists():
            print(f"  ! skill missing for {dept}: {skill_path}")
            mandate = "(skill file not found)"
        else:
            mandate = _extract_mandate(sp.read_text(encoding="utf-8"))

        mem_dir = VAULT / dept / "_memory" / agent
        mem_dir.mkdir(parents=True, exist_ok=True)

        # soul.md always refreshed from the current skill mandate.
        (mem_dir / "soul.md").write_text(_soul(dept, agent, mandate), encoding="utf-8")
        # memory.md / user.md only created if absent (never clobber learning).
        mf = mem_dir / "memory.md"
        if not mf.exists():
            mf.write_text(_MEMORY_INIT, encoding="utf-8")
        uf = mem_dir / "user.md"
        if not uf.exists():
            uf.write_text(_USER_INIT, encoding="utf-8")

        seeded += 1
        print(f"  seeded {dept:8s} -> {mem_dir}")

    print(f"\nseeded {seeded} agent memory triads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
