
from src.log_reader import parse_daily_log


def test_parses_daily_log_entries(tmp_path):
    f = tmp_path / "2026-04-27.md"
    f.write_text(
        """
## 14:23 · @U123 · proposal: chg_4421
**Q:** What's the LCR?
**A:** LCR is 118.50%
**Citations:** liq.pdf:p3
**Confidence:** 0.91
**Outcome:** approved

## 15:01 · @U456 · proposal: none
**Q:** Show me the NSFR
**A:** NSFR is 104.2%
**Citations:**
**Confidence:** 0.85
**Outcome:** pending
""",
        encoding="utf-8",
    )
    entries = parse_daily_log(f)
    assert len(entries) == 2
    assert entries[0].outcome == "approved"
    assert entries[0].proposal_id == "chg_4421"
    assert entries[0].confidence == 0.91
    assert entries[1].proposal_id is None


def test_empty_file_returns_empty(tmp_path):
    f = tmp_path / "empty.md"
    f.write_text("", encoding="utf-8")
    assert parse_daily_log(f) == []


def test_missing_file_returns_empty(tmp_path):
    assert parse_daily_log(tmp_path / "nonexistent.md") == []


def test_parses_latency_format(tmp_path):
    """CEO orchestrator emits Latency not Confidence — should parse without error."""
    f = tmp_path / "2026-05-21.md"
    f.write_text(
        """
## 05:46 · @u · proposal: none
**Q:** what is your task
**A:** I am an AI agent.
**Latency:** 1187ms
**Outcome:** n/a
""",
        encoding="utf-8",
    )
    entries = parse_daily_log(f)
    assert len(entries) == 1
    assert entries[0].confidence == 0.0  # latency field does not set confidence
    assert entries[0].outcome == "n/a"
    assert entries[0].proposal_id is None
