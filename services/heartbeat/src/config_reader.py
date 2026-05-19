import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_enabled_departments(config_path: str) -> list[dict]:
    """Load departments.json and return only those with heartbeat.enabled=true."""
    path = Path(config_path)
    if not path.exists():
        log.warning("departments.json not found at %s", config_path)
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    departments = data.get("departments", [])

    # Handle both dict and list formats
    if isinstance(departments, dict):
        dept_list = [{"dept_id": k, **v} for k, v in departments.items()]
    else:
        dept_list = departments

    enabled = []
    for dept in dept_list:
        hb = dept.get("heartbeat", {})
        if hb.get("enabled", False):
            enabled.append(dept)

    return enabled
