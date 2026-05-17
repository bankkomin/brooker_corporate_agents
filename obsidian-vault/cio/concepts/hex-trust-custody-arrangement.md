---
title: "Hex Trust Custody Arrangement & Fee Schedule"
type: "concept"
department: "cio"
status: "under_review"
sources: ["Brooker Group_ Custody Fee Supplement - Hex Trust Limited (HK)_March2026.docx", "HT_Markets_MTA_Review_Memo.docx"]
source_file: "Brooker Group_ Custody Fee Supplement - Hex Trust Limited (HK)_March2026.docx"
related: ["hex-trust", "ht-markets-trading-arrangement", "ht-markets-svg", "hex-trust-kyc-requirements", "2026-04-22-ht-markets-mta-review", "capital-sovereignty-doctrine"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"
coverage: "high"
tags: ["cio", "concept", "custody", "fees", "digital-asset", "hex-trust"]
---

# Hex Trust Custody Arrangement & Fee Schedule

## Summary

The custody side of the Brooker–Hex Trust relationship: a Fee Supplement to the Hex Safe
v2 Custodian Agreement, signed by Brooker International Company Limited ([[bicl]]) with
**HEX TRUST LIMITED (HK)** in March 2026. Unlike the [[ht-markets-trading-arrangement|HT
Markets MTA]] (a title-transfer trading contract), this is the regulated custody track
recommended by the [[2026-04-22-ht-markets-mta-review|contract review memo]] for holding
idle treasury digital assets.

## Custody Fee Schedule

Custody fees are quoted in basis points (bps) per annum, calculated daily at noon UTC,
accrued each calendar day against the asset balance, and invoiced monthly.

| Service | Fee |
|---------|-----|
| Account Opening / Onboarding | Waived |
| Transition Period | Custody fees waived for 3 months after signing |
| Custody — $0 to $10M AUC | 8 bps |
| Custody — $10M to $50M AUC | 6 bps |
| Custody — $50M to $100M AUC | 4 bps |
| Custody — $100M+ AUC | 2 bps |
| Withdrawal Fee | 0.5 bps (0.005%) per external withdrawal |
| Custody Fee Waiver | Custody fees waived in any month with **$5M USD notional** deployed into Hex Trust Earn / Structured Solutions (assessed monthly) |

**Invoicing start:** the earlier of (a) the date the client's Wallet is delivered on
Hex Safe, or (b) 30 days after the date of the Fee Supplement.

## Insurance

Hex Trust maintains insurance with an **aggregate limit of US$50,000,000** across all
clients (subject to deductibles, exclusions and limitations). Coverage can be extended to
**US$100M** subject to Lead Insurer agreement.

## Signatories

- **Client:** Varut Bulakul, for and on behalf of Brooker International Company Limited
- **Custodian:** Hex Trust Limited (HK)

## Why It Matters

The custody arrangement is the structurally safer half of the Hex Trust relationship.
The [[2026-04-22-ht-markets-mta-review]] recommends a **two-track structure**: long-term
treasury holdings sit here under the regulated HK custody entity (bailment/trust
structure), while only working capital actively deployed in options/derivatives goes
through the [[ht-markets-trading-arrangement|HT Markets SVG MTA]]. The custody account
is also a fast-cash channel under the [[capital-sovereignty-doctrine]] (pledge crypto
for a dollar loan).

## Related Concepts

- [[hex-trust]] — the custodian entity
- [[ht-markets-trading-arrangement]] — the separate (riskier) trading contract
- [[hex-trust-kyc-requirements]] — onboarding documents required to open the account
- [[2026-04-22-ht-markets-mta-review]] — the review memo recommending this two-track split

## Sources

- `Brooker Group_ Custody Fee Supplement - Hex Trust Limited (HK)_March2026.docx`
- `HT_Markets_MTA_Review_Memo.docx` (Section 7.1 — two-track recommendation)

## Agent Notes

The custody fee waiver triggers at $5M USD deployed into Hex Trust Earn each month —
relevant when sizing a yield deployment. AUC tiers are marginal-style bands quoted per
annum. Distinguish this regulated HK custody entity from HT Markets (SVG).
