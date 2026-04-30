#!/usr/bin/env python3
"""Re-run baseline queries against the live orchestrator and diff responses.

Exits 0 if no semantic regression; 1 if answers diverge beyond tolerance.

Usage:
    python scripts/diff_golden_master.py --orchestrator cac --baseline tests/baselines/cac-golden-fixtures/
"""
import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

import requests

PORTS = {"cac": 3001, "hr": 3002}


def main():
    ap = argparse.ArgumentParser(description="Compare live orchestrator responses against golden-master fixtures")
    ap.add_argument("--orchestrator", required=True, choices=PORTS.keys())
    ap.add_argument("--baseline", required=True, help="Directory containing baseline fixture JSON files")
    ap.add_argument("--threshold", type=float, default=0.85,
                    help="Minimum SequenceMatcher ratio for response text (default: 0.85)")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    base = Path(args.baseline)
    if not base.exists():
        print(f"ERROR: baseline directory not found: {base}", file=sys.stderr)
        sys.exit(2)

    port = PORTS[args.orchestrator]
    url = f"http://localhost:{port}/query"
    drift = []
    total = 0

    for fixture_file in sorted(base.glob("*.json")):
        recorded = json.loads(fixture_file.read_text())
        if recorded.get("error"):
            continue  # skip fixtures that failed during recording

        total += 1
        query = recorded["query"]
        print(f"  [{total}] {query[:60]}...", end=" ")

        try:
            resp = requests.post(url, json={"query": query}, timeout=args.timeout)
            resp.raise_for_status()
            live = resp.json()
        except requests.RequestException as e:
            drift.append({"fixture": fixture_file.name, "error": str(e)})
            print(f"ERROR ({e})")
            continue

        live_response = live.get("response", "")
        ratio = SequenceMatcher(None, recorded["response"], live_response).ratio()

        if ratio < args.threshold:
            drift.append({
                "fixture": fixture_file.name,
                "ratio": round(ratio, 3),
                "baseline_excerpt": recorded["response"][:160],
                "live_excerpt": live_response[:160],
            })
            print(f"DRIFT ({ratio:.2f})")
        else:
            print(f"OK ({ratio:.2f})")

    print()
    if drift:
        print(f"REGRESSION: {len(drift)} of {total} fixtures drifted beyond threshold {args.threshold}")
        for d in drift:
            print(f"  {d.get('fixture', '?')}: {d.get('ratio', 'error')}", file=sys.stderr)
            if "baseline_excerpt" in d:
                print(f"    baseline: {d['baseline_excerpt']}", file=sys.stderr)
                print(f"    live:     {d['live_excerpt']}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"OK — {total} fixtures within tolerance (threshold={args.threshold})")
        sys.exit(0)


if __name__ == "__main__":
    main()
