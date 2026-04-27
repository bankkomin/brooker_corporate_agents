---
title: "Capital Adequacy Ratio (CAR)"
type: "concept"
department: "cac"
sources: ["Basel III: A global regulatory framework for more resilient banks (BCBS 189)", "Local Banking Authority Prudential Standard CAP-1"]
related: ["cet1", "rwa", "icaap"]
created: "2026-04-10"
updated: "2026-04-10"
confidence: "high"
coverage: "high"
tags: ["capital", "basel-iii", "regulatory", "car", "capital-adequacy"]
---

# Capital Adequacy Ratio (CAR)

## Summary

The Capital Adequacy Ratio (CAR) measures a bank's total regulatory capital as a percentage of its Risk-Weighted Assets (RWA). It is the headline capital metric and is monitored daily by the CAC committee. The regulatory minimum is 8% under Basel III; Brooker Bank's internal target is 12.5%, reflecting additional buffers. Falling below the internal target triggers a Critical escalation.

## Definition

CAR = (Tier 1 Capital + Tier 2 Capital) / Risk-Weighted Assets × 100%

- **Tier 1 Capital:** Going-concern capital — primarily Common Equity Tier 1 (CET1) plus Additional Tier 1 (AT1) instruments
- **Tier 2 Capital:** Gone-concern capital — subordinated debt, general provisions, up to prescribed limits
- **RWA:** Risk-Weighted Assets across credit risk, market risk, and operational risk

Regulatory minimum (Basel III): 8%
Brooker Bank internal target: 12.5% (incorporating capital conservation buffer and internal buffer)

## How It Works

**Total Capital components:**

| Component | Minimum % of RWA | Notes |
|-----------|-----------------|-------|
| CET1 | 4.5% | Highest-quality capital |
| Additional Tier 1 (AT1) | + 1.5% = 6.0% Tier 1 total | Perpetual instruments |
| Tier 2 | + 2.0% = 8.0% total CAR | Subordinated debt |
| Capital Conservation Buffer | + 2.5% = 10.5% | Mandatory; restrictions on distributions if breached |
| Countercyclical Buffer (CCyB) | 0–2.5% (jurisdiction-dependent) | Set by macro-prudential authority |

**Brooker Bank internal target of 12.5%** incorporates:
- 8.0% minimum requirement
- 2.5% capital conservation buffer
- 2.0% internal management buffer (above regulatory floor)

CAR is calculated monthly for internal reporting and quarterly for regulatory submission.

## Why It Matters

CAR ensures that a bank has sufficient capital to absorb unexpected losses before depositors and creditors are exposed to loss. A bank with a low CAR is vulnerable to insolvency during stress events. Regulatory breach results in mandatory supervisory action, restrictions on dividends and buybacks, and potential licence conditions. The conservation buffer acts as a graduated restriction — partial breach triggers distribution limits before hard minimums are reached.

## Key Metrics / Thresholds

| Metric | Threshold | Frequency | Escalation |
|--------|-----------|-----------|------------|
| CAR (regulatory min) | ≥ 8.0% | Monthly / Quarterly | Critical if breached |
| CAR + conservation buffer | ≥ 10.5% | Monthly | High if breached |
| CAR internal target | ≥ 12.5% | Monthly | Critical if below |
| CAR approaching warning | < 13.5% (100bps above target) | Monthly | Medium |
| Tier 1 ratio | ≥ 6.0% | Monthly | Critical if breached |

## Related Concepts

- [[cet1]] — The highest-quality component of Tier 1 capital; most closely watched by regulators
- [[rwa]] — The denominator; rising RWA compresses CAR even if capital is unchanged
- [[icaap]] — Internal Capital Adequacy Assessment Process; stress-tests CAR under adverse scenarios

## Source References

- BCBS, "Basel III: A global regulatory framework for more resilient banks", revised June 2011 (BCBS 189)
- Local Banking Authority Prudential Standard CAP-1
- ALCO Tracker, Capital tab, cell D8

## Agent Notes

- The capital-agent reads CAR from ALCO Tracker cell D8 (Capital tab).
- Report CAR as: "CAR of 14.20% exceeds the 12.5% internal target by 170bps and the 8.0% regulatory minimum by 620bps."
- If CAR < 12.5%, raise a Critical escalation immediately.
- Always cite the source calculation components (Tier 1 + Tier 2 capital, RWA figures) when proposing an update.
- Do not confuse total CAR with CET1 ratio — they have different minimums and different regulatory consequences.
