---
title: "Concentration Policy"
type: "concept"
department: "ic"
sources: ["IC meeting notes", "Investment Holding Policy"]
related: ["red-flag-policy", "investment-holding-limit"]
created: "2026-05-06"
updated: "2026-05-06"
confidence: "high"
coverage: "high"
tags: ["policy", "risk", "concentration", "single-name"]
---

# Concentration Policy

## Summary

A single position must not exceed **25% of the total investment portfolio** measured at MTM. Concentration breaches and Red Flag positions are tracked as separate sub-sections of the Master Sheet at every IC meeting.

## Definition

```
Position MTM / Total Investment Portfolio MTM  >  25%   →  CONCENTRATION BREACH
```

The denominator is the line **Total Investments** on the IC Dashboard.

## Asset-class ratios (companion limits)

The single-name 25% rule is layered on top of asset-class ratios:

| Class | Ratio | Cap | Source |
|-------|-------|-----|--------|
| Equity (incl. VC) | varies | max 60% | Dashboard `Ratio Equity` |
| Fix Income / Hybrid | varies | max 30% | Dashboard `Ratio Fix` |
| Structured Loan | varies | max 50% | Dashboard `Ratjio Structured Loan` |
| Digital Asset Treasury | varies | max 50% | Dashboard `Ratio Digital Asset Treasury` |

Cross-reference into `[[dashboard-2026-02]]` for the latest ratios.

## Why It Matters

A concentration breach signals over-exposure to single-issuer risk. When a Red Flag position is also a concentration breach, the IC committee must produce a reduction plan within the same meeting and escalate to CEO if the reduction cannot be executed inside one quarter.

## Related Concepts

- [[red-flag-policy]] — companion -25% loss test
- [[investment-holding-limit]] — 40% Investment / Total Assets cap

## Source References

- IC Meeting #1 2025 (2025-01-23) — "CONCENTRATION >25% POLICY" subsection
- IC Meeting #2 2025 (2025-04-02) — "CONCENTRATION >25% POLICY: none"
- IC Meeting #1 2026 (2026-03-19) — "CONCENTRATION >25% POLICY: none"

## Agent Notes

- Read `Total Investments` (Dashboard row 32) and divide each holding MTM by it.
- A position that is BOTH Red Flag AND concentration-breaching triggers a **Critical** escalation.
- "none" is a valid status — agents must affirmatively report "no concentration breaches" rather than silently omitting the section.
