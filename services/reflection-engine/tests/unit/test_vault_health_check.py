"""Unit tests for vault_health_check.

Builds a synthetic vault with intentional flaws and asserts each
check fires with the expected severity and code.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.vault_health_check import (
    Severity,
    aggregate_dept_lint,
    append_log_entry,
    check_broken_skill_links,
    check_duplicate_entities,
    check_empty_scaffolds,
    check_interdept_links,
    check_missing_dept_index,
    check_missing_tldr,
    check_root_index_drift,
    check_stale_decisions,
    check_stale_recency_markers,
    run_health_check,
    write_health_report,
    _existing_dept_dirs,
    _parse_frontmatter,
    _resolve_wikilink,
)


# ---------------------------------------------------------------------------
# Fixture: synthetic vault with intentional issues
# ---------------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Build a minimal vault with every check tripped at least once."""
    v = tmp_path / "obsidian-vault"
    v.mkdir()

    # Root index — references cac/index and (broken) ghost dept that doesn't exist
    (v / "index.md").write_text(
        "# Vault\n"
        "- [[cac/index|CAC]]\n"
        "- [[finance/index|Finance]]\n",
        encoding="utf-8",
    )
    (v / "log.md").write_text("# Log\n", encoding="utf-8")

    # cac dept — has index, has a note with broken skill link + stale claim + missing tldr
    cac = v / "cac"
    (cac / "concepts").mkdir(parents=True)
    (cac / "entities").mkdir()
    (cac / "decisions").mkdir()
    (cac / "daily-logs").mkdir()
    (cac / "_memory").mkdir()
    (cac / "index.md").write_text("# CAC\n- [[cac/concepts/foo]]\n", encoding="utf-8")
    (cac / "daily-logs" / ".gitkeep").touch()
    (cac / "_memory" / ".gitkeep").touch()

    (cac / "concepts" / "foo.md").write_text(
        "---\ntype: concept\n---\n\n"
        "# Foo\n\n"
        "## Summary\nSomething here.\n\n"
        "Some claim (as of 2023-01, oldsource.com) that is way too old.\n"
        "See [[skills/cac/nonexistent-skill]] for context.\n"
        "Also link to [[finance/entities/bicl]] which doesn't exist.\n",
        encoding="utf-8",
    )
    # entity present in cac
    (cac / "entities" / "bicl.md").write_text(
        "---\ntype: entity\n---\n# BICL (CAC view)\n",
        encoding="utf-8",
    )
    # decision past its review_date
    (cac / "decisions" / "2025-01-01-old.md").write_text(
        "---\ntype: decision\nreview_date: 2025-06-01\n---\n# Decision: Old\n",
        encoding="utf-8",
    )
    # decision with TL;DR section
    (cac / "decisions" / "2026-05-01-current.md").write_text(
        "---\ntype: decision\nreview_date: 2027-01-01\n---\n"
        "# Decision: Current\n\n## TL;DR for Agents\n**Retrieved by:** x\n",
        encoding="utf-8",
    )

    # finance — exists but no index.md (triggers missing-dept-index)
    finance = v / "finance"
    (finance / "entities").mkdir(parents=True)
    (finance / "entities" / "bicl.md").write_text(
        "---\ntype: entity\n---\n# BICL (Finance view)\n",
        encoding="utf-8",
    )

    # legal — exists but not linked from root index (triggers root-index-drift)
    legal = v / "legal"
    legal.mkdir()
    (legal / "index.md").write_text("# Legal\n", encoding="utf-8")

    # skills layout: cac/ has only one real skill
    skills_cac = v / "skills" / "cac"
    skills_cac.mkdir(parents=True)
    (skills_cac / "alm-review.md").write_text("---\nname: alm-review\n---\n# ALM\n", encoding="utf-8")

    # per-dept lint-report so aggregate_dept_lint has something to parse
    (cac / "lint-report.md").write_text(
        "## Critical\n- something bad\n\n## Warning\n- one\n- two\n\n## Info\n- minor\n",
        encoding="utf-8",
    )

    return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_parse_frontmatter_missing_returns_empty():
    fm, body = _parse_frontmatter("# no frontmatter\nbody")
    assert fm == {}
    assert "no frontmatter" in body


def test_parse_frontmatter_malformed_yaml_does_not_crash():
    text = "---\nthis: : : broken\n---\nbody"
    fm, body = _parse_frontmatter(text)
    assert fm == {}
    assert body == "body"


def test_parse_frontmatter_well_formed():
    text = "---\ntype: concept\ndept: cac\n---\nthe body"
    fm, body = _parse_frontmatter(text)
    assert fm == {"type": "concept", "dept": "cac"}
    assert body == "the body"


def test_resolve_wikilink_direct_file(vault: Path):
    p = _resolve_wikilink("cac/index", vault)
    assert p is not None and p.name == "index.md"


def test_resolve_wikilink_folder_with_index(vault: Path):
    p = _resolve_wikilink("cac/", vault)
    assert p is not None and p.name == "index.md"


def test_resolve_wikilink_missing(vault: Path):
    assert _resolve_wikilink("cac/nope", vault) is None


def test_existing_dept_dirs_skips_skills_and_templates(vault: Path):
    depts = _existing_dept_dirs(vault)
    assert "cac" in depts
    assert "finance" in depts
    assert "legal" in depts
    assert "skills" not in depts
    assert "templates" not in depts


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def test_check_broken_skill_links_fires(vault: Path):
    findings = check_broken_skill_links(vault)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity is Severity.CRITICAL
    assert f.code == "broken-skill-link"
    assert "skills/cac/nonexistent-skill" in f.detail


def test_check_interdept_links_fires(vault: Path):
    depts = _existing_dept_dirs(vault)
    findings = check_interdept_links(vault, depts)
    # finance has no index.md (deliberate for the missing-dept-index check),
    # so root index's [[finance/index|Finance]] is a broken inter-dept link.
    # Other inter-dept links in the fixture (cac/concepts/foo, finance/entities/bicl) resolve.
    broken = [f for f in findings if f.code == "broken-interdept-link"]
    assert len(broken) == 1
    assert "finance/index" in broken[0].detail
    assert broken[0].path == "index.md"


def test_check_interdept_links_detects_truly_broken(tmp_path: Path):
    v = tmp_path / "v"
    (v / "cac").mkdir(parents=True)
    (v / "ic").mkdir()
    (v / "cac" / "index.md").write_text(
        "# CAC\nReference: [[ic/decisions/never-existed]]\n",
        encoding="utf-8",
    )
    depts = _existing_dept_dirs(v)
    findings = check_interdept_links(v, depts)
    codes = [f.code for f in findings]
    assert "broken-interdept-link" in codes


def test_check_missing_dept_index_fires(vault: Path):
    findings = check_missing_dept_index(vault)
    codes = [(f.code, f.path) for f in findings]
    assert ("missing-dept-index", "finance/index.md") in codes


def test_check_root_index_drift_fires(vault: Path):
    depts = _existing_dept_dirs(vault)
    findings = check_root_index_drift(vault, depts)
    drifted = [f.path for f in findings if f.code == "root-index-drift"]
    # legal exists but not linked in root index
    assert any("legal" in f.detail for f in findings)


def test_check_root_index_drift_missing_root_index(tmp_path: Path):
    v = tmp_path / "v"
    v.mkdir()
    findings = check_root_index_drift(v, set())
    assert len(findings) == 1
    assert findings[0].code == "missing-root-index"
    assert findings[0].severity is Severity.CRITICAL


def test_check_duplicate_entities_fires(vault: Path):
    findings = check_duplicate_entities(vault)
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "duplicate-entity-name"
    assert f.path == "bicl.md"
    assert "cac/entities/" in f.detail
    assert "finance/entities/" in f.detail


def test_check_stale_decisions_fires(vault: Path):
    findings = check_stale_decisions(vault, today=date(2026, 5, 26))
    stale = [f for f in findings if f.code == "stale-decision"]
    assert len(stale) == 1
    assert "2025-01-01-old.md" in stale[0].path


def test_check_stale_decisions_skips_future(vault: Path):
    findings = check_stale_decisions(vault, today=date(2026, 5, 26))
    for f in findings:
        assert "2026-05-01-current.md" not in f.path


def test_check_empty_scaffolds_counts_correctly(vault: Path):
    findings = check_empty_scaffolds(vault)
    details = " ".join(f.detail for f in findings)
    assert "daily-logs" in details
    assert "_memory" in details


def test_check_stale_recency_markers_fires(vault: Path):
    findings = check_stale_recency_markers(vault, today=date(2026, 5, 26))
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "stale-claim"
    assert "as of 2023-01" in f.detail
    # 2023-01 -> 2026-05 is 40 months
    assert "40 months" in f.detail


def test_check_stale_recency_markers_ignores_recent(tmp_path: Path):
    v = tmp_path / "v"
    (v / "research" / "concepts").mkdir(parents=True)
    (v / "research" / "concepts" / "x.md").write_text(
        "Recent claim (as of 2026-04, foo.com) is fine.\n",
        encoding="utf-8",
    )
    findings = check_stale_recency_markers(v, today=date(2026, 5, 26))
    assert findings == []


def test_check_missing_tldr_rolls_up(vault: Path):
    findings = check_missing_tldr(vault)
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "missing-tldr"
    # 1 concept (foo) + 2 decisions, 1 decision has TL;DR
    # foo concept missing tldr, 2025 decision missing, 2026 decision has it
    # so 2 of 3 missing
    assert "2 of 3" in f.detail


def test_aggregate_dept_lint_parses_counts(vault: Path):
    rollup = aggregate_dept_lint(vault)
    assert rollup["cac"] == {"critical": 1, "warning": 2, "info": 1}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def test_run_health_check_aggregates_all(vault: Path):
    report = run_health_check(vault, today=date(2026, 5, 26))
    assert report.depts_scanned == 3  # cac, finance, legal
    assert report.notes_scanned > 0
    assert report.critical_count >= 1  # broken-skill-link
    assert report.warning_count >= 1  # missing-dept-index / root-index-drift
    assert report.info_count >= 1     # at least empty-scaffold / stale-claim
    codes = {f.code for f in report.findings}
    assert "broken-skill-link" in codes
    assert "missing-dept-index" in codes
    assert "stale-claim" in codes
    assert "missing-tldr" in codes


def test_run_health_check_clean_vault(tmp_path: Path):
    v = tmp_path / "v"
    v.mkdir()
    (v / "index.md").write_text("# Empty vault\n", encoding="utf-8")
    (v / "log.md").write_text("# Log\n", encoding="utf-8")
    report = run_health_check(v, today=date(2026, 5, 26))
    assert report.critical_count == 0
    assert report.warning_count == 0
    # No depts -> no findings
    assert len(report.findings) == 0


def test_write_health_report_creates_file(vault: Path):
    report = run_health_check(vault, today=date(2026, 5, 26))
    out = write_health_report(vault, report)
    assert out.exists()
    assert out.name == "2026-05-26.md"
    content = out.read_text(encoding="utf-8")
    assert "Vault Health Report" in content
    assert "## Critical" in content


def test_append_log_entry_appends_when_findings(vault: Path):
    report = run_health_check(vault, today=date(2026, 5, 26))
    log_path = vault / "log.md"
    before = log_path.read_text(encoding="utf-8")
    assert append_log_entry(vault, report) is True
    after = log_path.read_text(encoding="utf-8")
    assert "health-check" in after
    assert len(after) > len(before)


def test_append_log_entry_skips_on_zero_findings(tmp_path: Path):
    v = tmp_path / "v"
    v.mkdir()
    (v / "index.md").write_text("# Empty\n", encoding="utf-8")
    (v / "log.md").write_text("# Log\n", encoding="utf-8")
    report = run_health_check(v, today=date(2026, 5, 26))
    assert append_log_entry(v, report) is False
