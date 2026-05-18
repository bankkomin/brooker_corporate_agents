#!/usr/bin/env python3
"""Validate SKILL.md frontmatter (permissions, output_types) and cross-refs."""
import argparse, json, sys, re
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
KNOWN_MODES = {"read_only", "write_via_staging", "write_direct"}
KNOWN_OUTPUT_TYPES = {"text", "table", "checklist", "decision_tree", "calculation"}


def main():
    ap = argparse.ArgumentParser(description="Validate SKILL.md frontmatter and cross-references")
    ap.add_argument("--skill-dir", default=str(ROOT / "skills"))
    ap.add_argument("--inventory", default=str(ROOT / "config" / "document_inventory.json"))
    args = ap.parse_args()

    inv_path = Path(args.inventory)
    if inv_path.exists():
        inv = json.loads(inv_path.read_text(encoding="utf-8")).get("documents", [])
        known_collections = {d["qdrantCollection"] for d in inv} | {"shared_policies"}
    else:
        known_collections = set()
        print(f"WARN: inventory not found at {inv_path}, skipping collection cross-ref", file=sys.stderr)

    errors = []
    checked = 0
    skill_dir = Path(args.skill_dir)

    for f in skill_dir.rglob("*.md"):
        if f.name.startswith("_") or "history" in f.parts or "template" in str(f):
            continue
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue  # not a skill file (no frontmatter)
        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError as e:
            errors.append(f"{f.relative_to(skill_dir)}: yaml parse error: {e}")
            continue

        if not isinstance(fm, dict):
            continue

        checked += 1

        # shared_skills references must resolve to existing skill files
        for ref in fm.get("shared_skills") or []:
            ref_path = skill_dir / f"{ref}.md"
            if not ref_path.exists():
                errors.append(f"{f.relative_to(skill_dir)}: shared_skills entry "
                              f"'{ref}' does not resolve to a file under {skill_dir}")

        # investment-cluster skills must be content-only (read_only, no outbound)
        if "investment-cluster" in f.parts:
            ic_perms = fm.get("permissions")
            if not isinstance(ic_perms, dict) or ic_perms.get("mode") != "read_only":
                errors.append(f"{f.relative_to(skill_dir)}: investment-cluster skills "
                              f"must declare permissions.mode 'read_only'")
            if isinstance(ic_perms, dict) and ic_perms.get("outbound_apis"):
                errors.append(f"{f.relative_to(skill_dir)}: investment-cluster skills "
                              f"must declare an empty outbound_apis list")

        perms = fm.get("permissions")
        if perms is None:
            continue  # old-format skill without permissions block — skip until migration

        if isinstance(perms, dict):
            mode = perms.get("mode")
            if mode not in KNOWN_MODES:
                errors.append(f"{f.relative_to(skill_dir)}: permissions.mode '{mode}' invalid, "
                              f"expected one of {KNOWN_MODES}")
            if known_collections:
                for col in perms.get("read_collections", []):
                    if col not in known_collections:
                        errors.append(f"{f.relative_to(skill_dir)}: read_collections '{col}' "
                                      f"not in document_inventory")

        for ot in fm.get("output_types", ["text"]):
            if ot not in KNOWN_OUTPUT_TYPES:
                errors.append(f"{f.relative_to(skill_dir)}: output_types '{ot}' unknown, "
                              f"expected one of {KNOWN_OUTPUT_TYPES}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK — {checked} skill files validated")


if __name__ == "__main__":
    main()
