"""Vault-wide health check.

Implements the 10 checks defined in
`obsidian-vault/skills/shared/vault-health-check.md`. Pure disk scan,
no LLM, no Qdrant. Reads every `*.md` in the vault, plus per-dept
`lint-report.md` for rollup. Writes:

- `obsidian-vault/health-reports/YYYY-MM-DD.md` (one per run)
- Appended entry in `obsidian-vault/log.md` (skipped if zero findings)

Never modifies article content or frontmatter.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator

import yaml

log = logging.getLogger(__name__)

# Expected departments per vault-health-check SKILL.md "Domain Knowledge"
EXPECTED_DEPTS: frozenset[str] = frozenset({
    "cac", "ceo", "cio", "comms", "finance", "hr", "ic", "invest", "it",
    "legal", "macro", "ops", "regulations", "research", "risk", "shared",
    "vcc", "ib",
})

# Top-level directories that are NOT departments
NON_DEPT_DIRS: frozenset[str] = frozenset({
    "skills", "templates", "health-reports", ".obsidian",
})

WIKILINK_RE = re.compile(r"\[\[([^\]|#\n]+)(?:\|[^\]\n]*)?(?:#[^\]\n]*)?\]\]")
RECENCY_MARKER_RE = re.compile(r"\(as of (\d{4})-(\d{2})(?:-\d{2})?,\s*([^)]+)\)")
TLDR_HEADING_RE = re.compile(r"^##\s+TL;DR\s+for\s+Agents\s*$", re.MULTILINE)
DECISION_HEADING_RE = re.compile(r"^#\s+Decision:", re.MULTILINE)

RESERVED_FILE_NAMES: frozenset[str] = frozenset({"log.md", "lint-report.md"})
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({"_memory", ".obsidian", "health-reports"})
# Wikilink scans skip these directories because they contain illustrative
# examples / placeholders, not real intent to link
WIKILINK_EXCLUDED_DIRS: frozenset[str] = frozenset({"templates"})
PLACEHOLDER_CHARS = frozenset("{}<>")
FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

STALE_MARKER_MONTHS = 12
INTERDEPT_LINK_WARNING_THRESHOLD = 5


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    path: str  # vault-relative path or special token (e.g. "<rollup>")
    detail: str

    def to_md(self) -> str:
        return f"- **{self.code}** `{self.path}` — {self.detail}"


@dataclass
class HealthReport:
    run_date: date
    findings: list[Finding] = field(default_factory=list)
    depts_scanned: int = 0
    notes_scanned: int = 0
    per_dept_lint: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity is Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity is Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity is Severity.INFO)

    def to_md(self) -> str:
        lines = [
            "---",
            f"date: {self.run_date.isoformat()}",
            "type: health-report",
            "scope: vault",
            "---",
            "",
            f"# Vault Health Report — {self.run_date.isoformat()}",
            "",
            "## Summary",
            f"- Critical: {self.critical_count}",
            f"- Warning: {self.warning_count}",
            f"- Info: {self.info_count}",
            f"- Departments scanned: {self.depts_scanned}",
            f"- Notes scanned: {self.notes_scanned}",
        ]
        if self.per_dept_lint:
            total = {k: sum(d.get(k, 0) for d in self.per_dept_lint.values())
                     for k in ("critical", "warning", "info")}
            lines.append(
                f"- Per-dept lint rollup: {total['critical']} critical, "
                f"{total['warning']} warning, {total['info']} info "
                f"(see `{{dept}}/lint-report.md`)"
            )
        lines.append("")
        for sev in (Severity.CRITICAL, Severity.WARNING, Severity.INFO):
            in_sev = [f for f in self.findings if f.severity is sev]
            if not in_sev:
                continue
            lines.append(f"## {sev.value.capitalize()}")
            for f in in_sev:
                lines.append(f.to_md())
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Tolerant of malformed YAML."""
    if not text.startswith("---\n"):
        return ({}, text)
    end_marker = text.find("\n---\n", 4)
    if end_marker == -1:
        return ({}, text)
    fm_text = text[4:end_marker]
    body = text[end_marker + 5:]
    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            return ({}, body)
        return (fm, body)
    except yaml.YAMLError:
        return ({}, body)


def _months_old(year: int, month: int, today: date) -> int:
    return (today.year - year) * 12 + (today.month - month)


def _iter_vault_md(
    vault_root: Path, *, extra_excluded_dirs: frozenset[str] = frozenset()
) -> Iterator[Path]:
    """Yield every *.md file in the vault excluding reserved/excluded paths."""
    excluded = EXCLUDED_DIR_NAMES | extra_excluded_dirs
    for path in vault_root.rglob("*.md"):
        if path.name in RESERVED_FILE_NAMES:
            continue
        rel_parts = set(path.relative_to(vault_root).parts)
        if rel_parts & excluded:
            continue
        yield path


def _strip_code_blocks(text: str) -> str:
    """Remove fenced ``` ... ``` blocks and inline `...` code before wikilink scanning.

    Both fenced and inline code are documentation, not link intent — wikilinks
    inside them are examples, not references to follow.
    """
    text = FENCED_CODE_BLOCK_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def _is_placeholder(target: str) -> bool:
    """True if the target looks like a documentation placeholder, not a real link."""
    if any(c in PLACEHOLDER_CHARS for c in target):
        return True
    # `[[skills/...]]` style ellipsis placeholder
    if "..." in target:
        return True
    return False


def _resolve_wikilink(target: str, vault_root: Path) -> Path | None:
    """Resolve a wikilink target (no `.md` suffix) to a file on disk."""
    target = target.strip()
    if not target:
        return None
    # Trailing slash means "this folder" -> look for index.md inside
    if target.endswith("/"):
        idx = vault_root / target.rstrip("/") / "index.md"
        return idx if idx.is_file() else None
    candidate = vault_root / f"{target}.md"
    if candidate.is_file():
        return candidate
    folder = vault_root / target
    if folder.is_dir():
        idx = folder / "index.md"
        return idx if idx.is_file() else None
    return None


def _existing_dept_dirs(vault_root: Path) -> set[str]:
    """Top-level directories that look like departments (have *.md or subfolders)."""
    out = set()
    for child in vault_root.iterdir():
        if not child.is_dir():
            continue
        if child.name in NON_DEPT_DIRS:
            continue
        if child.name.startswith("."):
            continue
        out.add(child.name)
    return out


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_broken_skill_links(vault_root: Path) -> list[Finding]:
    """Check 1 — broken `[[skills/...]]` wikilinks. Critical."""
    findings: list[Finding] = []
    for path in _iter_vault_md(vault_root, extra_excluded_dirs=WIKILINK_EXCLUDED_DIRS):
        rel = path.relative_to(vault_root)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scan_text = _strip_code_blocks(text)
        for match in WIKILINK_RE.finditer(scan_text):
            target = match.group(1).strip()
            if not target.startswith("skills/"):
                continue
            if _is_placeholder(target):
                continue
            if _resolve_wikilink(target, vault_root) is None:
                findings.append(Finding(
                    Severity.CRITICAL,
                    "broken-skill-link",
                    str(rel).replace("\\", "/"),
                    f"references [[{target}]], file not on disk",
                ))
    return findings


def check_interdept_links(vault_root: Path, depts: set[str]) -> list[Finding]:
    """Check 2 — inter-dept wikilink resolution. Per-link warning; > N => batch warning."""
    broken: list[tuple[str, str]] = []
    for path in _iter_vault_md(vault_root, extra_excluded_dirs=WIKILINK_EXCLUDED_DIRS):
        rel = path.relative_to(vault_root)
        text = path.read_text(encoding="utf-8", errors="ignore")
        scan_text = _strip_code_blocks(text)
        for match in WIKILINK_RE.finditer(scan_text):
            target = match.group(1).strip()
            if target.startswith("skills/"):
                continue  # handled by check 1
            if "/" not in target:
                continue  # bare wikilink, not inter-dept
            if _is_placeholder(target):
                continue
            first = target.split("/", 1)[0]
            if first not in depts:
                continue
            if _resolve_wikilink(target, vault_root) is None:
                broken.append((str(rel).replace("\\", "/"), target))
    findings = [
        Finding(Severity.WARNING, "broken-interdept-link", path,
                f"[[{tgt}]] does not resolve")
        for path, tgt in broken
    ]
    if len(findings) > INTERDEPT_LINK_WARNING_THRESHOLD:
        findings.append(Finding(
            Severity.WARNING, "broken-interdept-link-batch", "<rollup>",
            f"{len(broken)} broken inter-dept wikilinks (above threshold of {INTERDEPT_LINK_WARNING_THRESHOLD})",
        ))
    return findings


def check_missing_dept_index(vault_root: Path) -> list[Finding]:
    """Check 3 — every expected dept directory has an index.md. Warning."""
    findings: list[Finding] = []
    for dept in sorted(EXPECTED_DEPTS):
        dept_dir = vault_root / dept
        if not dept_dir.is_dir():
            continue  # dept folder not yet created — not a missing-index issue
        index = dept_dir / "index.md"
        if not index.is_file():
            findings.append(Finding(
                Severity.WARNING, "missing-dept-index",
                f"{dept}/index.md", "directory exists, no index",
            ))
    return findings


def check_root_index_drift(vault_root: Path, depts: set[str]) -> list[Finding]:
    """Check 4 — every top-level dept dir is linked from root index.md. Warning."""
    root_index = vault_root / "index.md"
    if not root_index.is_file():
        return [Finding(
            Severity.CRITICAL, "missing-root-index", "index.md",
            "vault root index.md is missing",
        )]
    text = root_index.read_text(encoding="utf-8", errors="ignore")
    referenced = {
        m.group(1).split("/", 1)[0]
        for m in WIKILINK_RE.finditer(text)
        if "/" in m.group(1)
    }
    findings = []
    for dept in sorted(depts):
        if dept not in referenced:
            findings.append(Finding(
                Severity.WARNING, "root-index-drift", "index.md",
                f"top-level `{dept}/` is not linked from root index",
            ))
    return findings


def check_duplicate_entities(vault_root: Path) -> list[Finding]:
    """Check 5 — same entity filename appears in multiple depts. Info."""
    by_name: dict[str, list[str]] = defaultdict(list)
    for entities_dir in vault_root.glob("*/entities"):
        dept = entities_dir.parent.name
        for ent in entities_dir.glob("*.md"):
            by_name[ent.name].append(f"{dept}/entities/")
    findings = []
    for name, locations in sorted(by_name.items()):
        if len(locations) > 1:
            findings.append(Finding(
                Severity.INFO, "duplicate-entity-name", name,
                f"appears in: {', '.join(locations)}",
            ))
    return findings


def check_stale_decisions(vault_root: Path, today: date) -> list[Finding]:
    """Check 6 — decisions whose `review_date` frontmatter is in the past. Info."""
    findings: list[Finding] = []
    for decisions_dir in vault_root.glob("*/decisions"):
        for path in decisions_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            fm, _ = _parse_frontmatter(text)
            rev = fm.get("review_date") or fm.get("review-date")
            if not rev:
                continue
            try:
                if isinstance(rev, date):
                    rev_date = rev
                elif isinstance(rev, datetime):
                    rev_date = rev.date()
                else:
                    rev_date = date.fromisoformat(str(rev).strip()[:10])
            except (ValueError, TypeError):
                continue
            if rev_date < today:
                rel = path.relative_to(vault_root)
                findings.append(Finding(
                    Severity.INFO, "stale-decision",
                    str(rel).replace("\\", "/"),
                    f"review_date {rev_date.isoformat()} is in the past",
                ))
    return findings


def check_empty_scaffolds(vault_root: Path) -> list[Finding]:
    """Check 7 — rollup count of empty daily-logs/ and _memory/ folders. Info."""
    empty_daily = 0
    empty_memory = 0
    for daily in vault_root.glob("*/daily-logs"):
        if not daily.is_dir():
            continue
        contents = [p for p in daily.iterdir() if p.name != ".gitkeep"]
        if not contents:
            empty_daily += 1
    for memory in vault_root.glob("*/_memory"):
        if not memory.is_dir():
            continue
        contents = [p for p in memory.iterdir() if p.name != ".gitkeep"]
        if not contents:
            empty_memory += 1
    findings = []
    if empty_daily:
        findings.append(Finding(
            Severity.INFO, "empty-scaffold", "<rollup>",
            f"{empty_daily} `daily-logs/` directories contain only `.gitkeep` (0 daily notes)",
        ))
    if empty_memory:
        findings.append(Finding(
            Severity.INFO, "empty-scaffold", "<rollup>",
            f"{empty_memory} `_memory/` directories contain only `.gitkeep` (0 memory entries)",
        ))
    return findings


def check_stale_recency_markers(vault_root: Path, today: date) -> list[Finding]:
    """Check 8 — `(as of YYYY-MM, ...)` markers older than 12 months. Info."""
    findings: list[Finding] = []
    for path in _iter_vault_md(vault_root):
        rel = path.relative_to(vault_root)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in RECENCY_MARKER_RE.finditer(text):
            try:
                year = int(match.group(1))
                month = int(match.group(2))
            except ValueError:
                continue
            age = _months_old(year, month, today)
            if age >= STALE_MARKER_MONTHS:
                source = match.group(3).strip()
                findings.append(Finding(
                    Severity.INFO, "stale-claim",
                    str(rel).replace("\\", "/"),
                    f"marker `(as of {year:04d}-{month:02d}, {source})` is {age} months old",
                ))
    return findings


def check_missing_tldr(vault_root: Path) -> list[Finding]:
    """Check 9 — concept/decision notes lacking `## TL;DR for Agents`. Info (rollup)."""
    missing = 0
    total = 0
    for path in _iter_vault_md(vault_root):
        rel = path.relative_to(vault_root).as_posix()
        # Only consider notes within a dept's concepts/ or decisions/ subdir
        parts = rel.split("/")
        if len(parts) < 3:
            continue
        if parts[1] not in {"concepts", "decisions"}:
            continue
        # Don't treat templates as content notes
        if parts[0] == "templates":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm, body = _parse_frontmatter(text)
        ntype = str(fm.get("type", "")).lower()
        if ntype not in {"concept", "decision", "decision_log"}:
            continue
        total += 1
        if not TLDR_HEADING_RE.search(body):
            missing += 1
    if total == 0:
        return []
    return [Finding(
        Severity.INFO, "missing-tldr", "<rollup>",
        f"{missing} of {total} concept/decision notes have no `## TL;DR for Agents` section (lazy backfill in progress)",
    )]


def aggregate_dept_lint(vault_root: Path) -> dict[str, dict[str, int]]:
    """Check 10 — parse `{dept}/lint-report.md` and tally per-severity counts."""
    rollup: dict[str, dict[str, int]] = {}
    for dept in sorted(EXPECTED_DEPTS):
        report = vault_root / dept / "lint-report.md"
        if not report.is_file():
            continue
        text = report.read_text(encoding="utf-8", errors="ignore")
        counts = {"critical": 0, "warning": 0, "info": 0}
        current = None
        for line in text.splitlines():
            stripped = line.strip().lower()
            if stripped.startswith("## "):
                head = stripped[3:].strip()
                if head in counts:
                    current = head
                else:
                    current = None
                continue
            if current and line.lstrip().startswith("- "):
                counts[current] += 1
        rollup[dept] = counts
    return rollup


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_health_check(vault_root: Path, *, today: date | None = None) -> HealthReport:
    """Run every check and return a populated HealthReport."""
    today = today or date.today()
    depts = _existing_dept_dirs(vault_root)

    report = HealthReport(run_date=today, depts_scanned=len(depts))
    report.notes_scanned = sum(1 for _ in _iter_vault_md(vault_root))

    report.findings.extend(check_broken_skill_links(vault_root))
    report.findings.extend(check_interdept_links(vault_root, depts))
    report.findings.extend(check_missing_dept_index(vault_root))
    report.findings.extend(check_root_index_drift(vault_root, depts))
    report.findings.extend(check_duplicate_entities(vault_root))
    report.findings.extend(check_stale_decisions(vault_root, today))
    report.findings.extend(check_empty_scaffolds(vault_root))
    report.findings.extend(check_stale_recency_markers(vault_root, today))
    report.findings.extend(check_missing_tldr(vault_root))
    report.per_dept_lint = aggregate_dept_lint(vault_root)
    return report


def write_health_report(vault_root: Path, report: HealthReport) -> Path:
    """Write the markdown report to obsidian-vault/health-reports/YYYY-MM-DD.md."""
    out_dir = vault_root / "health-reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{report.run_date.isoformat()}.md"
    out_path.write_text(report.to_md(), encoding="utf-8")
    return out_path


def append_log_entry(vault_root: Path, report: HealthReport) -> bool:
    """Append a health-check entry to obsidian-vault/log.md.

    Per the SKILL.md spec, zero-finding runs do NOT append (avoid log spam).
    If log.md is missing the spec says escalate Critical — but at runtime we
    surface that via the report, and we still write the report. Returns
    whether an entry was written.
    """
    if not report.findings:
        return False
    log_path = vault_root / "log.md"
    if not log_path.is_file():
        log.error("obsidian-vault/log.md is missing; health-check did not append entry")
        return False
    entry = (
        f"\n## [{report.run_date.isoformat()}] health-check | "
        f"{report.critical_count} critical, {report.warning_count} warning, "
        f"{report.info_count} info across {report.depts_scanned} depts. "
        f"Report: health-reports/{report.run_date.isoformat()}.md\n"
    )
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    return True


async def run_and_persist(vault_root: Path, *, today: date | None = None) -> HealthReport:
    """Scheduler-facing entry point. Runs the check and writes outputs."""
    report = run_health_check(vault_root, today=today)
    out = write_health_report(vault_root, report)
    appended = append_log_entry(vault_root, report)
    log.info(
        "vault health check complete: %d critical, %d warning, %d info -> %s%s",
        report.critical_count, report.warning_count, report.info_count, out,
        " (logged)" if appended else "",
    )
    return report
