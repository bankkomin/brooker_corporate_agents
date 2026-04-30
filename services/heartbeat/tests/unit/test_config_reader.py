from src.config_reader import load_enabled_departments


def test_filters_enabled_only(dept_config_path):
    enabled = load_enabled_departments(dept_config_path)
    assert len(enabled) == 1
    assert enabled[0]["dept_id"] == "finance"


def test_missing_file_returns_empty(tmp_path):
    enabled = load_enabled_departments(str(tmp_path / "nonexistent.json"))
    assert enabled == []


def test_all_disabled(tmp_path):
    import json
    p = tmp_path / "depts.json"
    p.write_text(json.dumps({"departments": [
        {"dept_id": "x", "heartbeat": {"enabled": False}},
    ]}))
    assert load_enabled_departments(str(p)) == []
