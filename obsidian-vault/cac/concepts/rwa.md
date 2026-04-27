---
title: "Risk-Weighted Assets (RWA)"
type: "concept"
department: "cac"
sources: ["Basel III: Finalising post-crisis reforms (BCBS 424)", "Local Banking Authority Prudential Standard CAP-3"]
related: ["car", "cet1", "icaap"]
created: "2026-04-10"
updated: "2026-04-10"
confidence: "high"
coverage: "high"
tags: ["capital", "basel-iii", "rwa", "risk-weights", "credit-risk", "market-risk", "operational-risk"]
---

# Risk-Weighted Assets (RWA)

## Summary

Risk-Weighted Assets (RWA) is the denominator of all key capital ratios (CAR, CET1, Tier 1). It represents the bank's total assets and off-balance-sheet exposures adjusted for risk, so that higher-risk exposures require proportionally more capital. A 15% quarter-over-quarter increase in RWA triggers a High escalation because it directly compresses capital ratios without any change in actual capital.

## Definition

RWA = Credit Risk RWA + Market Risk RWA + Operational Risk RWA

Each component aggregates exposures multiplied by their prescribed risk weights. The risk weights are determined by either the Standardised Approach (SA) or Internal Ratings-Based Approach (IRB), subject to regulatory approval.

## How It Works

**1. Credit Risk RWA (typically the largest component — 70–80% of total RWA):**

Under the Standardised Approach, each exposure class has prescribed risk weights:

| Exposure Type | Standardised Risk Weight |
|---------------|--------------------------|
| Sovereign (AAA to AA-) | 0% |
| Sovereign (A+ to A-) | 20% |
| Sovereign (BBB+ to BBB-) | 50% |
| Banks (investment grade) | 20–50% |
| Corporate (BBB- and above) | 75–100% |
| Retail mortgages (≤ 80% LTV) | 35% |
| Consumer / personal loans | 75% |
| Non-performing loans | 150% |
| Equity investments | 100–250% |

Under IRB, risk weights are derived from the bank's own PD, LGD, and EAD models.

**2. Market Risk RWA:**

Covers trading book exposures to interest rate, equity, foreign exchange, and commodity price movements. Calculated via the Standardised Approach for market risk or the Internal Models Approach (IMA).

**3. Operational Risk RWA:**

Under the Basel IV Standardised Approach for Operational Risk (replacing AMA and BIA), RWA is driven by the bank's Business Indicator (BI) and historical loss data.

**RWA output floor (Basel IV — BCBS 424):**

From 2023 (phased to 2028), RWA from internal models cannot fall below 72.5% of the SA-calculated RWA. This prevents excessive optimisation of internal models.

## Why It Matters

RWA is the leverage point for capital management. Growing the loan book increases credit risk RWA, compressing CAR and CET1 ratios. Conversely, shedding risk (selling assets, synthetic hedging) reduces RWA and improves ratios. The committee uses RWA trend analysis to:
1. Understand capital consumption by business line
2. Identify whether ratio changes are driven by capital changes vs. portfolio growth
3. Ensure the RWA output floor remains above the 72.5% threshold

A rapid RWA increase (> 15% QoQ) may indicate unplanned credit growth, a model recalibration, or a deterioration of existing exposures to higher risk-weight bands.

## Key Metrics / Thresholds

| Metric | Threshold | Frequency | Escalation |
|--------|-----------|-----------|------------|
| RWA total | Monitored vs. capital plan | Monthly | Informational |
| RWA QoQ increase | > 15% | Quarterly | High (24h) |
| RWA output floor compliance | ≥ 72.5% of SA RWA | Quarterly | Critical if breached |
| Credit RWA as % of total | Tracked for concentration | Monthly | Informational |

## Related Concepts

- [[car]] — CAR = Total Capital / RWA; RWA is the denominator
- [[cet1]] — CET1 Ratio = CET1 Capital / RWA; same denominator relationship
- [[icaap]] — ICAAP stress tests project RWA under adverse macroeconomic scenarios

## Source References

- BCBS, "Basel III: Finalising post-crisis reforms" (Basel IV), December 2017 (BCBS 424)
- BCBS, "Calculation of RWA for credit risk" (CRE), consolidated standards
- Local Banking Authority Prudential Standard CAP-3
- ALCO Tracker, Capital tab, cell D11

## Agent Notes

- The capital-agent reads RWA from ALCO Tracker cell D11 (Capital tab).
- Report RWA in millions to 1 decimal place: "Total RWA of $4,218.3M, up 3.2% from prior quarter."
- When reporting capital ratios, always state both the capital figure and the RWA to make the ratio transparent.
- A quarterly RWA increase > 15% triggers a High escalation — investigate whether the driver is credit portfolio growth, rating migrations, model changes, or new trading book positions.
- Never update RWA in the ALCO Tracker without citing the source calculation (credit report, regulatory return, or ICAAP model run).
