#!/usr/bin/env python3
"""Validate config/departments.json + config/document_inventory.json against schemas + cross-references."""
import argparse, json, sys
from pathlib import Path

try:
    from jsonschema import validate, ValidationError
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description="Validate config JSON files against schemas and cross-references")
    ap.add_argument("--departments", default=str(ROOT / "config" / "departments.json"))
    ap.add_argument("--departments-schema", default=str(ROOT / "config" / "departments.schema.json"))
    ap.add_argument("--inventory", default=str(ROOT / "config" / "document_inventory.json"))
    ap.add_argument("--inventory-schema", default=str(ROOT / "config" / "document_inventory.schema.json"))
    args = ap.parse_args()

    errors = []

    # Validate departments
    dept_schema = json.loads(Path(args.departments_schema).read_text(encoding="utf-8"))
    depts_data = json.loads(Path(args.departments).read_text(encoding="utf-8"))

    # Handle both old format (nested object) and new format (array)
    if "departments" in depts_data and isinstance(depts_data["departments"], dict):
        # Old format: departments is an object keyed by dept_id
        depts = []
        for dept_id, dept_obj in depts_data["departments"].items():
            row = {"dept_id": dept_id, **dept_obj}
            depts.append(row)
    elif "departments" in depts_data and isinstance(depts_data["departments"], list):
        depts = depts_data["departments"]
    else:
        depts = []
        errors.append("departments.json: missing or invalid 'departments' key")

    # Only validate individual dept rows if schema has per-dept validation
    dept_item_schema = dept_schema.get("properties", {}).get("departments", {}).get("items")
    if dept_item_schema:
        for d in depts:
            try:
                validate(d, dept_item_schema)
            except ValidationError as e:
                errors.append(f"dept {d.get('dept_id', '?')}: {e.message}")

    # Validate inventory
    inv_path = Path(args.inventory)
    if inv_path.exists():
        inv_schema = json.loads(Path(args.inventory_schema).read_text(encoding="utf-8"))
        inv_data = json.loads(inv_path.read_text(encoding="utf-8"))
        inv = inv_data.get("documents", [])
        dept_ids = {d.get("dept_id", d.get("name", "").lower()) for d in depts}

        for row in inv:
            try:
                validate(row, inv_schema)
            except ValidationError as e:
                errors.append(f"doc {row.get('id', '?')}: {e.message}")
                continue
            if row["ownerDept"] not in dept_ids and row["ownerDept"] != "ceo":
                errors.append(f"doc {row['id']}: ownerDept '{row['ownerDept']}' not in departments.json")
            if not row["qdrantCollection"].startswith(row["ownerDept"]):
                errors.append(f"doc {row['id']}: collection '{row['qdrantCollection']}' "
                              f"should start with ownerDept '{row['ownerDept']}'")

        # Cross-ref: crossReadAccess targets must be known depts
        all_known = dept_ids | {"ceo"}
        for d in depts:
            for cra in d.get("crossReadAccess", []):
                if cra not in all_known and cra != "*":
                    errors.append(f"dept {d.get('dept_id', '?')}: crossReadAccess '{cra}' not a known dept")
    else:
        print(f"SKIP: inventory file not found at {inv_path}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK — {len(depts)} depts, {len(inv) if inv_path.exists() else 0} docs validated")


if __name__ == "__main__":
    main()
