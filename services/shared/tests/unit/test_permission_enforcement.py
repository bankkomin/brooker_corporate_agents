import pytest

from services.shared.permission_enforcement import (
    PermissionError,
    ensure_can_write,
    validate_collections,
)


def test_read_only_skill_blocks_staging_writer():
    perms = {"mode": "read_only", "data_zones": [1], "outbound_apis": [], "read_collections": ["cac_docs"]}
    with pytest.raises(PermissionError):
        ensure_can_write(perms, action="staging_proposal")


def test_write_via_staging_allows():
    perms = {"mode": "write_via_staging", "data_zones": [1, 2], "outbound_apis": [], "read_collections": []}
    ensure_can_write(perms, action="staging_proposal")  # should not raise


def test_validate_collections_finds_unknown():
    perms = {"read_collections": ["cac_docs", "imaginary_collection"]}
    unknown = validate_collections(perms, known_collections={"cac_docs", "shared_policies"})
    assert "imaginary_collection" in unknown


def test_validate_collections_all_known():
    perms = {"read_collections": ["cac_docs", "shared_policies"]}
    unknown = validate_collections(perms, known_collections={"cac_docs", "shared_policies"})
    assert unknown == []
