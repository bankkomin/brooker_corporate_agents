---
title: "Common Equity Tier 1 (CET1) Ratio"
type: "concept"
department: "cac"
sources: ["Basel III: A global regulatory framework for more resilient banks (BCBS 189)", "Local Banking Authority Prudential Standard CAP-2"]
related: ["car", "rwa", "icaap"]
created: "2026-04-10"
updated: "2026-04-10"
confidence: "high"
coverage: "high"
tags: ["capital", "basel-iii", "regulatory", "cet1", "capital-adequacy"]
---

# Common Equity Tier 1 (CET1) Ratio

## Summary

The Common Equity Tier 1 (CET1) ratio is the most stringent measure of a bank's capital strength. It compares the highest-quality, loss-absorbing capital — ordinary shares, retained earnings, and other comprehensive income — against Risk-Weighted Assets. Regulators and markets treat CET1 as the primary indicator of solvency. Brooker Bank's minimum CET1 including all buffers is 10.5%, with the hard regulatory floor at 4.5%.

## Definition

CET1 Ratio = CET1 Capital / Risk-Weighted Assets × 100%

**CET1 Capital includes:**
- Ordinary share capital and share premium (common stock issued under applicable accounting standards)
- Retained earnings
- Accumulated other comprehensive income (AOCI), subject to regulatory filters
- Other disclosed reserves

**Deductions from CET1 (key items):**
- Goodwill and other intangible assets
- Deferred tax assets reliant on future profitability
- Defined benefit pension fund deficits
- Significant investments in financial institutions above prescribed limits

CET1 capital is "going concern" capital — it absorbs losses before the bank fails. It is the first and most important layer in the Basel III capital stack.

## How It Works

**Basel III capital stack and CET1 position:**

| Requirement Layer | Minimum CET1 | Implication |
|-------------------|-------------|-------------|
| Pillar 1 minimum | 4.5% | Hard floor; breach triggers regulatory action |
| + Capital conservation buffer | + 2.5% = 7.0% | Mandatory; partial breach restricts distributions |
| + Countercyclical buffer (max) | + 2.5% = 9.5% | Set by macro-prudential authority |
| + Other Pillar 2 / D-SIB buffers | Firm-specific | Additional requirements from supervisory review |
| Brooker Bank internal target | 10.5% | Includes all buffers and internal management margin |

The capital conservation buffer operates as a graduated constraint. When CET1 falls into the buffer range (4.5%–7.0%), distribution restrictions are applied on a sliding scale:

| CET1 as % of RWA | Maximum distribution as % of earnings |
|------------------|---------------------------------------|
| 4.5% – 5.125% | 0% |
| 5.125% – 5.75% | 20% |
| 5.75% – 6.375% | 40% |
| 6.375% – 7.0% | 60% |
| > 7.0% | No restriction |

## Why It Matters

CET1 is the most scrutinised capital metric by regulators, rating agencies, and institutional investors. A declining CET1 trend signals capital erosion from losses, RWA growth, or excessive distributions. Unlike total CAR, CET1 cannot be bolstered by subordinated debt — only genuine equity-quality resources count. Stress tests (ICAAP) assess whether CET1 remains above minimums under adverse scenarios.

## Key Metrics / Thresholds

| Metric | Threshold | Frequency | Escalation |
|--------|-----------|-----------|------------|
| CET1 (regulatory hard floor) | ≥ 4.5% | Monthly / Quarterly | Critical — immediate |
| CET1 (with conservation buffer) | ≥ 7.0% | Monthly | Critical if breached — distributions restricted |
| CET1 internal target | ≥ 10.5% | Monthly | Critical if below |
| CET1 warning band | < 11.5% | Monthly | Medium — approaching |
| CET1 quarter-over-quarter decline | > 50bps | Quarterly | High (24h review) |

## Related Concepts

- [[car]] — Total capital adequacy ratio; CAR ≥ CET1 because it includes Tier 2
- [[rwa]] — The denominator; RWA growth can compress CET1 without any capital loss
- [[icaap]] — Annual internal stress test that projects CET1 under stressed scenarios

## Source References

- BCBS, "Basel III: A global regulatory framework for more resilient banks", revised June 2011 (BCBS 189)
- BCBS, "Basel III: Finalising post-crisis reforms", December 2017 (BCBS 424)
- Local Banking Authority Prudential Standard CAP-2
- ALCO Tracker, Capital tab, cell D9

## Agent Notes

- The capital-agent reads CET1 from ALCO Tracker cell D9 (Capital tab).
- Report CET1 as: "CET1 of 12.80% exceeds the 10.5% internal target by 230bps."
- If CET1 < 7.0% (below conservation buffer threshold), raise a Critical escalation — dividend and distribution restrictions apply.
- If CET1 is between 7.0% and 10.5%, raise a Medium flag and note the buffer consumption.
- Never conflate CET1 with total CAR when presenting capital adequacy to the committee.
- Deductions (goodwill, DTAs) can significantly reduce CET1 below gross equity — always verify the net figure.
