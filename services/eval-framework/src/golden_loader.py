from pathlib import Path

import yaml

from .config import settings


def load_golden_answers(dept_id: str) -> list[dict]:
    """Load golden answers from a YAML file for the given department."""
    path = Path(settings.EVAL_DATASET_PATH) / f"{dept_id}.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("golden_answers", []) if data else []
