---
title: "Net Stable Funding Ratio (NSFR)"
type: "concept"
department: "cac"
sources: ["Basel III: Net Stable Funding Ratio (BCBS 295)", "Local Banking Authority Prudential Standard LQD-2"]
related: ["lcr", "rwa", "duration-gap"]
created: "2026-04-10"
updated: "2026-04-10"
confidence: "high"
coverage: "high"
tags: ["liquidity", "basel-iii", "regulatory", "nsfr", "structural-liquidity"]
---

# Net Stable Funding Ratio (NSFR)

## Summary

The Net Stable Funding Ratio (NSFR) is a Basel III structural liquidity requirement designed to ensure that banks maintain a stable funding profile over a one-year horizon. Unlike the LCR (which covers a 30-day stress period), the NSFR addresses medium- and long-term funding stability. Brooker Bank must maintain an NSFR of at least 100% at all times. Breach is a Critical escalation.

## Definition

NSFR = (Available Stable Funding) / (Required Stable Funding) × 100%

- **Available Stable Funding (ASF):** Portion of capital and liabilities expected to be reliable over the one-year horizon. Each funding source is assigned an ASF factor (0–100%) reflecting its stability.
- **Required Stable Funding (RSF):** Amount of stable funding required based on the liquidity characteristics and residual maturities of assets and off-balance-sheet exposures. Each asset category is assigned an RSF factor.

NSFR ≥ 100% is required.

## How It Works

**Available Stable Funding (ASF) factors — key examples:**

| Funding Source | ASF Factor |
|----------------|------------|
| Tier 1 and Tier 2 regulatory capital | 100% |
| Stable retail deposits and term deposits ≥ 1 year | 95% |
| Less stable retail deposits | 90% |
| Wholesale funding (non-financial, maturity ≥ 1 year) | 50% |
| Wholesale funding (maturity < 6 months) | 0% |
| Short-term interbank funding (< 6 months) | 0% |

**Required Stable Funding (RSF) factors — key examples:**

| Asset Category | RSF Factor |
|----------------|------------|
| Cash and central bank reserves | 0% |
| Unencumbered Level 1 HQLA | 5% |
| Unencumbered Level 2A HQLA | 15% |
| Retail loans (maturity < 1 year) | 50% |
| Retail mortgages (maturity ≥ 1 year) | 65% |
| Corporate loans (maturity ≥ 1 year) | 65–85% |
| Illiquid assets / NPLs | 100% |

The NSFR ratio is calculated monthly and reported to the regulator quarterly.

## Why It Matters

NSFR prevents excessive reliance on short-term wholesale funding to finance long-dated assets — the structural mismatch that amplified the 2008 financial crisis. A falling NSFR signals that the funding profile is becoming less stable and may indicate rising rollover risk or asset-liability mismatch. It complements LCR by covering longer time horizons.

## Key Metrics / Thresholds

| Metric | Threshold | Frequency | Escalation |
|--------|-----------|-----------|------------|
| NSFR | ≥ 100% (regulatory minimum) | Monthly | Critical if < 100% |
| NSFR internal target | ≥ 110% | Monthly | Medium if < 110% |
| ASF / RSF gap trend | Declining > 5pp quarter-over-quarter | Quarterly | High |

## Related Concepts

- [[lcr]] — Short-term (30-day) liquidity stress metric; NSFR covers the 1-year horizon
- [[duration-gap]] — ALM concept related to asset-liability maturity mismatch
- [[rwa]] — RSF factors are calibrated to asset risk profiles

## Source References

- Basel Committee on Banking Supervision, "Basel III: the Net Stable Funding Ratio", October 2014 (BCBS 295)
- Local Banking Authority Prudential Standard LQD-2, current version
- ALCO Tracker, Liquidity tab, cell D11

## Agent Notes

- The liquidity-agent reads NSFR from ALCO Tracker cell D11 (Liquidity tab).
- Report NSFR as: "NSFR of 112.30% exceeds the 100% regulatory minimum by 12.30pp."
- If NSFR < 100%, raise a Critical escalation immediately.
- If NSFR is between 100% and 110%, raise a Medium flag and note the trend direction.
- When LCR and NSFR are both under pressure simultaneously, escalate both and note the compounding risk in the analysis narrative.
