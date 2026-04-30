#!/usr/bin/env python3
"""Record golden-master fixtures from a running orchestrator for regression testing.

Usage:
    python scripts/record_golden_master.py --orchestrator cac --output tests/baselines/cac-golden-fixtures/
    python scripts/record_golden_master.py --orchestrator hr --output tests/baselines/hr-golden-fixtures/
"""
import argparse
import json
import sys
from pathlib import Path

import requests

PORTS = {"cac": 3001, "hr": 3002}

CAC_QUERIES = [
    "What is the current LCR ratio?",
    "Show me the NSFR status",
    "What are the current funding facility utilization rates?",
    "Summarize the latest capital adequacy position",
    "What covenants are close to breach?",
    "What is the ALM gap analysis for 30-day bucket?",
    "Show the BG weekly report summary",
    "What is the current networth position?",
    "List all active funding facilities and their terms",
    "What escalations are pending for CAC committee?",
]

HR_QUERIES = [
    "What is the current headcount by department?",
    "Summarize the HR policy on annual leave",
    "What are the compensation bands for senior roles?",
    "Show recent talent acquisition pipeline status",
    "What is the employee turnover rate this quarter?",
    "Summarize the remuneration policy highlights",
    "What training programs are currently active?",
    "List pending HR escalations",
    "What is the policy on remote work?",
    "Show the organizational structure overview",
]


def main():
    ap = argparse.ArgumentParser(description="Record golden-master fixtures from a running orchestrator")
    ap.add_argument("--orchestrator", required=True, choices=PORTS.keys())
    ap.add_argument("--output", required=True, help="Output directory for fixture JSON files")
    ap.add_argument("--timeout", type=int, default=60, help="Request timeout in seconds")
    args = ap.parse_args()

    queries = CAC_QUERIES if args.orchestrator == "cac" else HR_QUERIES
    port = PORTS[args.orchestrator]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    url = f"http://localhost:{port}/query"
    success = 0

    for i, query in enumerate(queries):
        fixture_file = output / f"{i:02d}_{args.orchestrator}.json"
        print(f"[{i+1}/{len(queries)}] {query[:60]}...", end=" ")
        try:
            resp = requests.post(url, json={"query": query}, timeout=args.timeout)
            resp.raise_for_status()
            data = resp.json()
            fixture = {
                "query": query,
                "response": data.get("response", ""),
                "citations": data.get("citations", []),
                "confidence": data.get("confidence", 0.0),
                "agent": data.get("agent", ""),
            }
            fixture_file.write_text(json.dumps(fixture, indent=2))
            print(f"OK ({len(fixture['response'])} chars)")
            success += 1
        except requests.RequestException as e:
            print(f"FAIL ({e})")
            fixture = {"query": query, "response": "", "citations": [], "confidence": 0.0, "error": str(e)}
            fixture_file.write_text(json.dumps(fixture, indent=2))

    print(f"\nRecorded {success}/{len(queries)} fixtures to {output}")
    sys.exit(0 if success == len(queries) else 1)


if __name__ == "__main__":
    main()
