---
title: "Liquidity Coverage Ratio (LCR)"
type: "concept"
department: "cac"
sources: ["Basel III: The Liquidity Coverage Ratio and liquidity risk monitoring tools (BCBS 238)", "Local Banking Authority Prudential Standard LQD-1"]
related: ["nsfr", "hqla", "liquidity-analysis"]
created: "2026-04-10"
updated: "2026-04-10"
confidence: "high"
coverage: "high"
tags: ["liquidity", "basel-iii", "regulatory", "lcr"]
---

# Liquidity Coverage Ratio (LCR)

## Summary

The Liquidity Coverage Ratio (LCR) is a Basel III regulatory requirement that mandates banks hold a sufficient stock of unencumbered High-Quality Liquid Assets (HQLA) to survive a severe 30-day liquidity stress scenario. Brooker Bank must maintain an LCR of at least 100% at all times. Breach of this threshold triggers an immediate Critical escalation.

## Definition

LCR = (Stock of HQLA) / (Total Net Cash Outflows over the next 30 calendar days) × 100%

The ratio must be greater than or equal to 100% as required by the regulator. An LCR of 100% means the bank holds exactly enough liquid assets to cover projected net outflows over the stress period. A ratio above 100% represents a liquidity buffer above the minimum.

## How It Works

**Step 1 — Calculate the HQLA stock:**

HQLA is divided into three tiers, each subject to haircuts and concentration limits:

| Tier | Examples | Haircut | Cap |
|------|----------|---------|-----|
| Level 1 | Cash, central bank reserves, sovereign bonds (0% RWA) | 0% | None |
| Level 2A | Sovereign bonds (20% RWA), covered bonds (AA-) | 15% | ≤ 40% of HQLA |
| Level 2B | RMBS (AA), corporate bonds (A-/BBB+), equities | 25–50% | ≤ 15% of HQLA |

**Step 2 — Calculate net cash outflows:**

Net Cash Outflows = Total Expected Cash Outflows − min(Total Expected Cash Inflows, 75% of Total Expected Cash Outflows)

Outflow rates are assigned based on counterparty type (e.g., retail deposits: 5–10%, unsecured wholesale: 25–100%).

**Step 3 — Divide and express as a percentage.**

## Why It Matters

A sub-100% LCR signals that the bank could not meet its obligations during a 30-day stress event without selling illiquid assets or seeking emergency funding. Breach triggers regulatory notification requirements, potential supervisory intervention, and immediate management action. Even approaching the 100% floor (e.g., LCR < 110%) warrants heightened monitoring.

## Key Metrics / Thresholds

| Metric | Threshold | Frequency | Escalation |
|--------|-----------|-----------|------------|
| LCR | ≥ 100% (regulatory minimum) | Daily | Critical if < 100% |
| LCR buffer warning | < 110% | Daily | Medium — approaching threshold |
| LCR internal target | ≥ 120% | Monthly reporting | Informational |
| HQLA concentration (Level 2B) | ≤ 15% of HQLA | Monthly | Review if exceeded |

## Related Concepts

- [[nsfr]] — The 1-year structural liquidity counterpart to LCR's 30-day stress metric
- [[hqla]] — Defines the eligible assets that populate the numerator of LCR
- [[rwa]] — Risk-weighted assets affect Level 1/2A classification of sovereign bonds

## Source References

- Basel Committee on Banking Supervision (BCBS), "Basel III: The Liquidity Coverage Ratio and liquidity risk monitoring tools", January 2013 (BCBS 238)
- Local Banking Authority Prudential Standard LQD-1, current version
- ALCO Tracker, Liquidity tab, cell D10

## Agent Notes

- The liquidity-agent reads LCR from ALCO Tracker cell D10 (Liquidity tab).
- When reporting LCR, always state the value relative to the 100% minimum: "LCR of 118.50% exceeds the regulatory minimum by 18.50pp."
- If LCR < 100%, raise a Critical escalation immediately — do not wait for confirmation.
- If LCR is between 100% and 110%, raise a Medium escalation flag.
- Source for any proposed LCR update must be a CFO report, audited liquidity statement, or regulatory filing — not Slack alone.
