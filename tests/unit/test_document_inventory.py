"""Tests for document_inventory.json schema validation."""
import json
from pathlib import Path

import pytest

try:
    from jsonschema import ValidationError, validate  # noqa: F401
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "config" / "document_inventory.schema.json"
DATA_PATH = ROOT / "config" / "document_inventory.json"


@pytest.fixture
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def documents():
    return json.loads(DATA_PATH.read_text(encoding="utf-8")).get("documents", [])


def test_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_inventory_file_exists():
    assert DATA_PATH.exists()


def test_inventory_loads_and_validates(schema, documents):
    for row in documents:
        validate(row, schema)


def test_inventory_has_all_owner_depts(documents):
    owners = {d["ownerDept"] for d in documents}
    expected = {"ceo", "finance", "ib", "hr", "ic", "cac", "cio", "legal", "risk", "vcc", "comms", "it"}
    missing = expected - owners
    assert not missing, f"Missing owner depts: {missing}"


def test_inventory_qdrant_collections_match_owner(documents):
    for row in documents:
        assert row["qdrantCollection"].startswith(row["ownerDept"]), \
            f"{row['id']}: collection '{row['qdrantCollection']}' doesn't start with owner '{row['ownerDept']}'"


def test_inventory_total_count(documents):
    assert len(documents) >= 50, f"Expected at least 50 docs, got {len(documents)}"


def test_inventory_ids_unique(documents):
    ids = [d["id"] for d in documents]
    assert len(ids) == len(set(ids)), "Duplicate document IDs found"


def test_inventory_tiers_valid(documents):
    valid_tiers = {"policy", "report", "tracker", "narrative"}
    for row in documents:
        assert row["tier"] in valid_tiers, f"{row['id']}: invalid tier '{row['tier']}'"
