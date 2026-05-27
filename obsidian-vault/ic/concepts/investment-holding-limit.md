---
title: "Investment Holding 40% Limit"
type: "concept"
department: "ic"
sources: ["IC meeting notes", "Bank of Thailand prudential guidance"]
related: ["concentration-policy", "investment-holding-40pct-limit"]
created: "2026-05-06"
updated: "2026-05-06"
confidence: "high"
coverage: "high"
tags: ["policy", "regulatory", "investment-holding", "bot"]
---

# Investment Holding 40% Limit

## Quick-answer aliases (for retrieval)

- **Q: Which dashboard column is the numerator for the 40% Investment Company rule?** A: **`Investment Company Baht`** — **column H, row 32** of `[[dashboard-2026-02]]` (value Bt 1,706,260,117.84). NOT `Total Investments` (col B = Bt 2,925,430,103.67) — using col B yields the wrong answer and is 2× off for BNB OTC.
- **Q: What is the formula for the 40% Investment Company rule?** A: `Investment Company Baht (col H, row 32) ÷ Total Assets Q4 Estimated (col B, row 38)` ≤ 40%. Published Q2 2026 ratio = 52.23%.
- **Q: When does the 40% rule become binding?** A: **30 June 2026** (end of 2-year grace period; value-chain carve-out proposed but denied).
- **Q: Why can't I just use the Total Investments column?** A: Because each holding has its own Investment-Company classification %: BNB OTC = 50.4% (so Bt 1 sold = Bt 0.50 numerator reduction); Digital Assets = 94.2%; listed Brooker portfolio = 100%. Using `Total Investments` skips this scaling.

## Summary

Investments may not exceed **40% of Total Assets**. The firm has been in a **2-year grace period** carrying excess investment exposure with the regulator's acknowledgement; the grace period **ends 30 June 2026**, after which the ratio must be brought below 40% via divestment, call options, or reclassification.

## Definition

```
Ratio = Total Investments / Total Assets   ≤   40%   (post-grace)
```

The strategic / synergy / value-chain carve-out was **proposed but not granted** for value-chain assets, leaving the headline cap binding.

## History

| Meeting | Investment / Total Assets | Status |
|---------|---------------------------|--------|
| 2025-01-23 | 54.5% (Q3 est.) | 2-yr grace, no new investment |
| 2025-04-02 | 56.9% (Q4 est.) | 2-yr grace, no new investment |
| 2026-03-19 | 52.8% (Q4 est.) | Grace ends 30 Jun 2026 — rebalance Q2 (sell + call option) |

## Strategic Carve-out (proposed)

The IC proposed excluding **strategic / synergy / value-chain** holdings from the ratio. The regulator granted partial recognition but **denied** the value-chain exclusion. The current effective denominator therefore includes all listed and non-listed equity exposures.

## Why It Matters

This is a **regulatory** ceiling, not an internal target. Crossing it post-grace would draw a Bank of Thailand intervention. The running [[investment-holding-40pct-limit]] decision file tracks every reduction lever (Sukhothai redemption, Brooker portfolio trim, structured loan rotation) against the deadline.

## Related Concepts

- [[concentration-policy]] — single-name 25% cap layered on top
- [[investment-holding-40pct-limit]] — running decision: how to land below 40% by 30 Jun 2026
- [[liquidity-management-policy]] — companion test on cash side

## Source References

- IC Meeting #1 2025 (2025-01-23) — "Investment Holding 40% of Assets"
- IC Meeting #2 2025 (2025-04-02) — "Investment Holding 40% of Assets"
- IC Meeting #1 2026 (2026-03-19) — "Investment Holding 40% of Assets. Grace finished June 30."

## Agent Notes

- The cap binds on **30 June 2026**. Any meeting after that date with a >40% ratio must trigger a **Critical** escalation, regardless of trajectory.
- The denominator is `Total Assets Q4 (Estimated)` from the dashboard.
- Acceptable reduction mechanisms: divestment, written call options, structured loan rotation. Reclassification alone is not acceptable absent regulatory blessing.
