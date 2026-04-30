import json
import pytest


@pytest.fixture
def dept_config_path(tmp_path):
    """Create a temporary departments.json for testing."""
    config = {
        "version": "2.0",
        "departments": [
            {
                "dept_id": "cac",
                "name": "CAC Committee",
                "live": True,
                "heartbeat": {"enabled": False, "schedule": "", "context_sources": [], "outbound_actions": []},
            },
            {
                "dept_id": "finance",
                "name": "Finance",
                "live": False,
                "heartbeat": {
                    "enabled": True,
                    "schedule": "0 8 * * 1-5",
                    "context_sources": ["sharepoint:Finance/Tracker", "slack:#finance-committee"],
                    "outbound_actions": ["draft_email", "post_slack_summary"],
                },
            },
        ],
    }
    p = tmp_path / "departments.json"
    p.write_text(json.dumps(config))
    return str(p)
