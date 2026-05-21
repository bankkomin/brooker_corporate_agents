"""Unit tests for skill_proposal_writer."""
from pathlib import Path

import pytest


def test_writes_proposal_file(tmp_path, monkeypatch):
    monkeypatch.setenv("REFLECTION_STAGING_PENDING_DIR", str(tmp_path))
    # Re-import after env is set so Settings picks it up
    import importlib
    import src.config as cfg_mod
    importlib.reload(cfg_mod)
    import src.skill_proposal_writer as spw_mod
    importlib.reload(spw_mod)

    proposals = [
        {
            "skill_path": "skills/cac/liquidity.md",
            "trigger": "5 consecutive low-signal LCR corrections",
            "evidence": {"count": 7, "avg_signal": 0.32},
        }
    ]
    written = spw_mod.write_skill_proposals("cac", "liquidity-agent", proposals)

    assert len(written) == 1
    fpath = Path(written[0])
    assert fpath.exists()
    content = fpath.read_text(encoding="utf-8")
    assert "skill-update-proposal" in content
    assert "liquidity-agent" in content
    assert "0.320" in content
    assert "/data/mirror/" not in content  # safety check


def test_empty_proposals_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("REFLECTION_STAGING_PENDING_DIR", str(tmp_path))
    import importlib
    import src.config as cfg_mod
    importlib.reload(cfg_mod)
    import src.skill_proposal_writer as spw_mod
    importlib.reload(spw_mod)

    assert spw_mod.write_skill_proposals("cac", "liquidity-agent", []) == []


def test_unsafe_dept_id_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("REFLECTION_STAGING_PENDING_DIR", str(tmp_path))
    import importlib
    import src.config as cfg_mod
    importlib.reload(cfg_mod)
    import src.skill_proposal_writer as spw_mod
    importlib.reload(spw_mod)

    result = spw_mod.write_skill_proposals("../../etc", "agent", [{"trigger": "x", "evidence": {}}])
    assert result == []
