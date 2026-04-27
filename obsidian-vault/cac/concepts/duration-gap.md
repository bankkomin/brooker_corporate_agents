---
title: "Duration Gap"
type: "concept"
department: "cac"
sources: ["BCBS Standards: Interest Rate Risk in the Banking Book (IRRBB, BCBS 368)", "Local Banking Authority IRRBB Guidance Note IG-4"]
related: ["nsfr", "lcr", "nii-sensitivity", "eve-sensitivity"]
created: "2026-04-10"
updated: "2026-04-10"
confidence: "high"
coverage: "high"
tags: ["alm", "interest-rate-risk", "irrbb", "duration", "asset-liability-management"]
---

# Duration Gap

## Summary

Duration gap is the primary Asset-Liability Management (ALM) metric that measures the mismatch between the interest-rate sensitivity of a bank's assets and its liabilities. A positive duration gap means assets are more sensitive to interest rate changes than liabilities — rising rates reduce the bank's economic value. Brooker Bank's internal threshold is a duration gap below 2.0 years; a gap exceeding 3.0 years triggers a Critical escalation.

## Definition

Duration Gap = Duration of Assets − (Total Liabilities / Total Assets) × Duration of Liabilities

Where "duration" refers to **modified duration** — the percentage change in the present value of a cash-flow stream for a 1% (100bps) change in interest rates.

A positive duration gap indicates the bank is asset-sensitive on a duration basis: a rise in interest rates reduces the market value of assets more than liabilities, compressing the Economic Value of Equity (EVE).

A negative duration gap means the bank is liability-sensitive: rising rates benefit EVE but may reduce Net Interest Income (NII) in the short run.

## How It Works

**Step 1 — Compute asset duration:**

Weighted average modified duration of all interest-earning assets, grouped by repricing bucket:

| Time Bucket | Examples |
|-------------|---------|
| Overnight – 30 days | Interbank loans, overnight repos, floating rate assets |
| 31 – 90 days | Short-term commercial loans |
| 91 – 365 days | Trade finance, short-term bonds |
| 1 – 5 years | Fixed-rate mortgages, corporate bonds |
| > 5 years | Long-term fixed mortgages, subordinated debt held |

**Step 2 — Compute liability duration:**

Weighted average modified duration of all interest-bearing liabilities (deposits, wholesale funding, issued bonds).

**Step 3 — Apply the duration gap formula.**

**Step 4 — Interpret against IRRBB stress scenarios:**

The duration gap drives NII sensitivity (+/- 100bps parallel shift) and EVE sensitivity (+/- 200bps shock). Both are monitored as separate KPIs.

**Practical example:**
- Asset duration: 3.8 years
- Liability duration: 1.2 years
- Liability / Asset ratio: 0.88
- Duration gap = 3.8 − (0.88 × 1.2) = 3.8 − 1.06 = **2.74 years**
- This exceeds the 2.0-year internal target and approaches the 3.0-year Critical threshold.

## Why It Matters

Duration gap directly quantifies the bank's exposure to interest rate movements. In a rising rate environment, a large positive gap causes:
1. Unrealised losses on the fixed-rate asset portfolio (EVE erosion)
2. Reduced margins on newly originated fixed-rate assets relative to higher funding costs
3. Potential forced selling of long-duration assets at a loss if liquidity is needed

Regulators under IRRBB (BCBS 368) require banks to monitor and limit both EVE and NII sensitivity, which are outputs of duration gap analysis.

## Key Metrics / Thresholds

| Metric | Threshold | Frequency | Escalation |
|--------|-----------|-----------|------------|
| Duration gap | < 2.0 years (internal target) | Monthly | Medium if 2.0–3.0 years |
| Duration gap | ≥ 3.0 years | Monthly | Critical — immediate |
| NII sensitivity (+100bps) | < 15% of net income | Monthly | High if exceeded |
| EVE sensitivity (+200bps) | < 20% of equity | Monthly | Critical if exceeded |
| Repricing gap (12-month cumulative) | Monitored by bucket | Monthly | Review if > ±10% of assets |

## Related Concepts

- [[nsfr]] — Structural funding stability; complements ALM duration analysis
- [[lcr]] — Short-term liquidity; impacted if duration mismatch forces asset sales
- [[car]] — EVE erosion from duration gap can reduce CET1 and CAR if realised

## Source References

- BCBS Standards: Interest Rate Risk in the Banking Book (IRRBB), April 2016 (BCBS 368)
- BCBS: Principles for the Management and Supervision of Interest Rate Risk, July 2004
- Local Banking Authority IRRBB Guidance Note IG-4
- ALCO Tracker, ALM tab, cell D8

## Agent Notes

- The alm-agent reads duration gap from ALCO Tracker cell D8 (ALM tab).
- Always express duration gap in years to 2 decimal places: "Duration gap of 2.74 years exceeds the 2.0-year internal target."
- If gap > 3.0 years, raise a Critical escalation immediately — note the specific asset and liability duration components.
- Report NII sensitivity with the explicit scenario: "NII sensitivity of -8.2% under a +100bps parallel rate shock."
- Report EVE sensitivity with scenario: "EVE sensitivity of -14.5% under a +200bps shock."
- Never mix up NII sensitivity (income statement impact) with EVE sensitivity (balance sheet / economic value impact).
- When proposing ALM tab updates, always cite the ALM model run date and version.
