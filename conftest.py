"""Root conftest — register hyphenated service directories as importable packages."""

import importlib
import sys
from pathlib import Path

# Map hyphenated directory names to valid Python identifiers so that
# ``from services.sync_mirror.src.connectors import ...`` works even
# though the directory on disk is ``services/sync-mirror/``.

_repo = Path(__file__).resolve().parent
_services = _repo / "services"

_HYPHEN_SERVICES = [
    "sync-mirror",
    "rag-ingestion",
    "sync-back",
    "cac-orchestrator",
    "approval-ui",
    "email-notifier",
    "slack-bot",
    "wiki-compiler",
]

for svc in _HYPHEN_SERVICES:
    svc_dir = _services / svc
    init_file = svc_dir / "__init__.py"
    if not svc_dir.is_dir() or not init_file.is_file():
        continue
    underscore = svc.replace("-", "_")
    mod_name = f"services.{underscore}"
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            mod_name,
            init_file,
            submodule_search_locations=[str(svc_dir)],
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
