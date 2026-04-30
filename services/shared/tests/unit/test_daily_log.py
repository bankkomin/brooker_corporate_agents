from services.shared.daily_log import log_interaction_node


def test_daily_log_appends_entry(tmp_path):
    state = {
        "vault_root": str(tmp_path),
        "dept_id": "cac",
        "user_id": "U123",
        "query": "what's the LCR?",
        "response": "LCR is 118.50%",
        "citations": ["doc:liq.pdf:p3"],
        "confidence": 0.91,
        "proposal_id": "chg_4421",
    }
    log_interaction_node(state)
    log_dir = tmp_path / "cac" / "daily-logs"
    files = list(log_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "what's the LCR?" in content
    assert "chg_4421" in content
    assert "0.91" in content
