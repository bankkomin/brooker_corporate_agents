---
title: ""
type: "concept"
department: ""
sources: []
related: []
created: ""
updated: ""
confidence: ""
coverage: ""
tags: []
---

# {{title}}

## Summary

One-paragraph plain-language summary of the concept.

## Definition

Precise definition, including any regulatory or technical basis.

## How It Works

Step-by-step or narrative explanation. Use tables and bullet lists for clarity.

## Why It Matters

Business or regulatory significance for the department.

## Key Metrics / Thresholds

| Metric | Threshold | Frequency |
|--------|-----------|-----------|
| | | |

## Related Concepts

- [[]] —

## Source References

- Source 1
- Source 2

## Recency Markers

Inline recency markers attach a date and source token to load-bearing factual claims so a future reader (human or agent) can spot stale facts at a glance. Required in `research/`, `regulations/`, `macro/` concepts; optional but encouraged elsewhere.

**Format:** `(as of YYYY-MM, <source-token>)` placed immediately after the claim.

**Source-token conventions:**
- Corporate file: `(as of 2026-02, ALCO_Tracker.xlsx)` — short filename from `O:\brooker_database` or vault `sources:` array
- Slack: `(as of 2026-04, #cac-committee | J. Doe)`
- External / web: `(as of 2026-01, sec.or.th)` — domain only, no full URL
- Meeting: `(as of 2026-02-21, Khao Yai retreat)` — date + named event

**Examples:**
- "BICL holds Bt 1,706mn in Investment Company assets (as of 2026-02, ALCO_Tracker.xlsx) against a Bt 4,265mn 40%-rule cap."
- "Thai SEC permits a 3-month post-IPO grace period before the 40% rule applies (as of 2026-01, sec.or.th)."
- "BNB OTC is 50.4% classified as Investment Company (as of 2026-02, ic-chair-agent skill v2.0)."

**When to mark vs. omit:**
- Mark: numeric thresholds, regulatory rules, counterparty positions, market data, any claim where staleness changes the decision
- Omit: framework definitions, named principles, historical events with a fixed date already in the sentence
- Frontmatter `source_date` covers the whole note; recency markers add per-claim precision

The `[[skills/shared/vault-health-check]]` skill scans for markers older than 12 months and reports them as info-level findings.

## Agent Notes

Notes for agents on how to use this concept in analysis or proposals.
