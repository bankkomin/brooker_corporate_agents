#!/usr/bin/env python3
"""Backfill the `## TL;DR for Agents` section on existing vault notes.

Reads the prioritised TODO list produced by `vault_convention_audit.py`
and, for each concept/decision note that's missing the section, calls
the LLM to draft a 3-line TL;DR (Retrieved by / Answers / Key facts).

Output mode is `--mode review` by default (recommended):
  * LLM drafts are written to `docs/tldr-drafts/{path}.md` as a
    self-contained review file showing the proposed insertion + the
    note's current first 60 lines for context. A human reads, edits,
    and applies them manually (copy/paste or a follow-up script).

Output mode `--mode staging` writes proper vault-staging manifests
(operation=update, target = original note path, draft_content = full
note with TL;DR inserted). HOD approves through the standard pipeline.

This script CHECKPOINTS progress to `.tldr_backfill_progress.json` so
a re-run skips notes whose drafts were already written. Safe to
interrupt + resume.

Usage:
    # Default: review mode, processes first 25 notes, writes to docs/tldr-drafts/
    python scripts/backfill_tldr.py

    # Process more in one run
    python scripts/backfill_tldr.py --limit 50

    # Specific dept only
    python scripts/backfill_tldr.py --dept research --limit 100

    # Stage manifests instead of writing review files
    python scripts/backfill_tldr.py --mode staging --staging-path /data/staging

    # Dry run — no LLM calls, just show what would be done
    python scripts/backfill_tldr.py --dry-run

Requires:
    LLM_BASE_URL, LLM_MODEL (e.g. http://nginx:8080/v1, qwen-122b)
    LLM_API_KEY (or `not-needed` for local vLLM)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = ROOT / "obsidian-vault"
DEFAULT_AUDIT = ROOT / "docs" / "vault-convention-backfill-todo.md"
DEFAULT_REVIEW_OUT = ROOT / "docs" / "tldr-drafts"
DEFAULT_CHECKPOINT = ROOT / ".tldr_backfill_progress.json"

TODO_ROW_RE = re.compile(r"^- \[ \] `([^`]+)` — (.+)$")
TITLE_HEADING_RE = re.compile(r"^# .+$", re.MULTILINE)
TLDR_HEADING_RE = re.compile(r"^##\s+TL;DR\s+for\s+Agents\s*$", re.MULTILINE)


PROMPT = """You write a 3-line `## TL;DR for Agents` preamble for a corporate knowledge note.

The note's frontmatter:
{frontmatter}

The note's body (truncated):
---
{body}
---

Return ONLY the TL;DR block in this EXACT shape, no fences, no commentary:

## TL;DR for Agents
**Retrieved by:** [[skills/{dept}/<skill-name>]]
**Answers:** "One quoted question this note resolves, max 12 words."
**Key facts:** 1-2 sentences naming the most decision-relevant facts. Use inline (as of YYYY-MM, source) markers for quantitative claims.

Rules:
- `Retrieved by:` must contain at least one `[[skills/<dept>/...]]` wikilink. If the dept has known skills (cac, ic), use a real one; otherwise leave as `[[skills/{dept}/]]`.
- `Answers:` must be a quoted question, ≤ 12 words.
- `Key facts:` ≤ 280 chars total. Cite recency for any percentage / amount / threshold.
- Do not invent facts. If the body has no quantitative content, write a qualitative summary."""


@dataclass
class BackfillItem:
    rel_path: str
    codes: set[str]


def parse_audit_todo(audit_path: Path) -> list[BackfillItem]:
    """Extract `- [ ]` rows from the audit markdown, filtering for `tldr` items."""
    if not audit_path.is_file():
        print(f"ERROR: audit file not found at {audit_path}", file=sys.stderr)
        sys.exit(2)
    out: list[BackfillItem] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        m = TODO_ROW_RE.match(line)
        if not m:
            continue
        rel = m.group(1)
        codes = {c.strip("` ") for c in m.group(2).split()}
        if "tldr" in codes:
            out.append(BackfillItem(rel_path=rel, codes=codes))
    return out


def load_checkpoint(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("done", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_checkpoint(path: Path, done: set[str]) -> None:
    payload = {"done": sorted(done), "updated": datetime.utcnow().isoformat()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return ({}, text)
    end = text.find("\n---\n", 4)
    if end == -1:
        return ({}, text)
    try:
        fm = yaml.safe_load(text[4:end]) or {}
        if not isinstance(fm, dict):
            return ({}, text[end + 5:])
        return (fm, text[end + 5:])
    except yaml.YAMLError:
        return ({}, text[end + 5:])


def has_tldr(body: str) -> bool:
    return bool(TLDR_HEADING_RE.search(body))


def insert_tldr_after_title(full_text: str, tldr_block: str) -> str:
    """Insert the tldr block on a new line after the first `# Title` heading,
    or at the start of the body if no heading exists."""
    fm, body = _parse_frontmatter(full_text)
    fm_prefix = full_text[: len(full_text) - len(body)] if fm else ""
    m = TITLE_HEADING_RE.search(body)
    if m:
        pos = m.end()
        new_body = body[:pos] + "\n\n" + tldr_block.rstrip() + "\n" + body[pos:]
    else:
        # No title heading. Frontmatter closes with `\n`; emit one blank line
        # then TL;DR then a blank line then the original body (sans leading newlines).
        new_body = "\n" + tldr_block.rstrip() + "\n\n" + body.lstrip("\n")
    return fm_prefix + new_body


async def draft_tldr(*, llm, item: BackfillItem, vault_root: Path) -> str | None:
    note_path = vault_root / item.rel_path
    if not note_path.is_file():
        print(f"  skipping (file gone): {item.rel_path}", file=sys.stderr)
        return None
    text = note_path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    if has_tldr(body):
        return None  # already done
    dept = (fm.get("department") or item.rel_path.split("/", 1)[0]).strip()
    fm_repr = "\n".join(f"  {k}: {v}" for k, v in list(fm.items())[:10])
    truncated = body[:2500]
    prompt = PROMPT.format(frontmatter=fm_repr or "(none)", body=truncated, dept=dept)
    raw = await llm(prompt)
    # Tolerate code fences
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    if not raw.lstrip().startswith("## TL;DR for Agents"):
        # Try to salvage: prepend if model only returned the bullet lines
        if "**Retrieved by:**" in raw and "**Answers:**" in raw:
            raw = "## TL;DR for Agents\n" + raw
        else:
            return None
    return raw


async def _call_llm(prompt: str) -> str:
    from langchain_openai import ChatOpenAI

    chat = ChatOpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        model=os.environ["LLM_MODEL"],
        api_key=os.environ.get("LLM_API_KEY", "not-needed"),
        temperature=0.1,
    )
    resp = await chat.ainvoke(prompt)
    return getattr(resp, "content", "") or ""


def write_review_file(*, item: BackfillItem, vault_root: Path, tldr: str, out_dir: Path) -> Path:
    note_path = vault_root / item.rel_path
    full = note_path.read_text(encoding="utf-8")
    body_head = "\n".join(full.splitlines()[:60])
    out_path = out_dir / (item.rel_path.replace("/", "__") + ".review.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        f"# Review: TL;DR backfill draft for `{item.rel_path}`\n\n"
        f"_Generated {date.today().isoformat()} by `scripts/backfill_tldr.py`._\n\n"
        f"## Proposed insertion (after the title heading)\n\n"
        f"```markdown\n{tldr}\n```\n\n"
        f"## Note context (first 60 lines)\n\n"
        f"```markdown\n{body_head}\n```\n",
        encoding="utf-8",
    )
    return out_path


async def write_staging_manifest(
    *, item: BackfillItem, vault_root: Path, tldr: str, staging_path: str,
    source_run_id: str,
) -> str | None:
    try:
        from services.shared.vault_staging import build_manifest, write_vault_staging
    except ImportError:
        sys.path.insert(0, str(ROOT))
        from services.shared.vault_staging import build_manifest, write_vault_staging  # type: ignore

    note_path = vault_root / item.rel_path
    full = note_path.read_text(encoding="utf-8")
    new_full = insert_tldr_after_title(full, tldr)
    dept = item.rel_path.split("/", 1)[0]
    manifest = build_manifest(
        agent="scripts.backfill_tldr",
        dept=dept,
        target_vault_path=item.rel_path,
        operation="update",
        draft_content=new_full,
        confidence=0.7,
        reasoning="Backfill TL;DR for Agents preamble per CLAUDE.md Wiki Conventions.",
        proposal_source="vault_automation",
        source_run_id=source_run_id,
        extracted_from=item.rel_path,
    )
    return await write_vault_staging(manifest, staging_path=staging_path)


async def amain(args: argparse.Namespace) -> int:
    audit = Path(args.audit)
    vault = Path(args.vault)
    items = parse_audit_todo(audit)
    if args.dept:
        items = [i for i in items if i.rel_path.startswith(args.dept + "/")]
    print(f"Found {len(items)} note(s) needing TL;DR in audit file.")

    checkpoint_path = Path(args.checkpoint)
    done = load_checkpoint(checkpoint_path)
    if done:
        print(f"Resuming — {len(done)} already done.")
    pending = [i for i in items if i.rel_path not in done]
    if args.limit and len(pending) > args.limit:
        pending = pending[: args.limit]
    print(f"Processing {len(pending)} note(s) this run (limit={args.limit}).")

    if args.dry_run:
        for i in pending:
            print(f"  would draft: {i.rel_path}")
        return 0

    if args.mode == "staging" and not args.staging_path:
        print("ERROR: --mode staging requires --staging-path", file=sys.stderr)
        return 2

    if not (os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL")):
        print("ERROR: LLM_BASE_URL and LLM_MODEL must be set.", file=sys.stderr)
        return 2

    review_out = Path(args.review_out)
    source_run_id = f"tldr_backfill_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    written = 0
    failed = 0
    for i, item in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] {item.rel_path}")
        try:
            tldr = await draft_tldr(llm=_call_llm, item=item, vault_root=vault)
            if tldr is None:
                print("    skipped (already has TL;DR or file gone or LLM gave nothing usable)")
                done.add(item.rel_path)
                continue
            if args.mode == "review":
                out = write_review_file(
                    item=item, vault_root=vault, tldr=tldr, out_dir=review_out,
                )
                print(f"    wrote review -> {out.relative_to(ROOT)}")
            else:
                pid = await write_staging_manifest(
                    item=item, vault_root=vault, tldr=tldr,
                    staging_path=args.staging_path, source_run_id=source_run_id,
                )
                if pid:
                    print(f"    staged proposal {pid}")
                else:
                    print("    staging failed")
                    failed += 1
                    continue
            done.add(item.rel_path)
            written += 1
        except Exception as exc:
            print(f"    ERROR: {exc}", file=sys.stderr)
            failed += 1
        # Save checkpoint every 10 items so a crash doesn't lose all progress
        if i % 10 == 0:
            save_checkpoint(checkpoint_path, done)

    save_checkpoint(checkpoint_path, done)
    print()
    print(f"Done. Drafted {written}, failed {failed}, total_complete {len(done)}.")
    if args.mode == "staging" and written:
        print(f"All proposals share source_run_id={source_run_id} for batch review.")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default=str(DEFAULT_VAULT))
    ap.add_argument("--audit", default=str(DEFAULT_AUDIT),
                    help="Path to vault-convention-backfill-todo.md")
    ap.add_argument("--mode", choices=["review", "staging"], default="review",
                    help="review = write side-by-side draft files; staging = write vault manifests")
    ap.add_argument("--staging-path", default=None,
                    help="Required for --mode staging; e.g. /data/staging")
    ap.add_argument("--review-out", default=str(DEFAULT_REVIEW_OUT))
    ap.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    ap.add_argument("--dept", default=None, help="Process only notes in this dept")
    ap.add_argument("--limit", type=int, default=25,
                    help="Max notes per run (default 25; use --limit 0 for all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.limit == 0:
        args.limit = None
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
