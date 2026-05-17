---
title: "HT Markets Crypto Trading & Options Arrangement (MTA)"
type: "concept"
department: "cio"
status: "under_review"
sources: ["Brooker Group Master Trading Agreement Template_SVG (March 2026).docx", "Brooker Group_MTA Supplement_Options and Margin_HT Markets (SVG) Limited(Mar 2026).docx", "HT_Markets_MTA_Review_Memo.docx"]
related: ["ht-markets-svg", "hex-trust", "hex-trust-custody-arrangement", "2026-04-22-ht-markets-mta-review", "dat-sell-call-strategy", "capital-sovereignty-doctrine"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"
coverage: "high"
tags: ["cio", "concept", "trading-agreement", "options", "custody", "digital-asset", "counterparty-risk"]
---

# HT Markets Crypto Trading & Options Arrangement (MTA)

## Summary

The contractual framework under which Brooker (via its Hong Kong subsidiary
[[bicl]] / Brooker International Company Limited) buys, sells and writes options on
cryptocurrency with **[[ht-markets-svg|HT Markets (SVG) Limited]]** — the trading arm
associated with the Hex Trust group. It consists of a Master Trading Agreement plus an
Options & Margin Supplement (both March 2026 templates). A separate
[[hex-trust-custody-arrangement|Hex Trust custody arrangement]] covers idle treasury
holdings. The arrangement supplies the option-writing venue contemplated by the IC's
[[dat-sell-call-strategy]].

## Document Set

| Document | Role |
|----------|------|
| Master Trading Agreement (MTA), Mar 2026 | OTC spot + forward crypto trading; 9 clauses, Schedules A–C |
| MTA Supplement — Options & Margin, Mar 2026 | Adds Call/Put options, rewrites termination/close-out, adds Schedules F–I |
| Custody Fee Supplement — Hex Trust Ltd (HK) | Separate custody fee schedule — see [[hex-trust-custody-arrangement]] |

**Document hierarchy:** Confirmations prevail over the Supplement; the Supplement
prevails over the MTA; Schedule I prevails over the rest for a given Transaction. The
terms that matter most for any trade sit in the Confirmation, which HT drafts unilaterally.

## How Trading Works

- **Orders:** either party (Offeror) sends a Sales / Purchase / Forward / Option Order
  through a Recognised Communication Channel; the Offeree accepts within an Acceptance
  Window. An Accepted Order is final, irreversible and binding.
- **Options (Supplement Schedule F–G):** European-style Call and Put options on
  cryptocurrency; physical or cash settlement. Cash settlement = MAX(Settlement − Strike, 0)
  × quantity for a call. The Option Buyer pays a Premium to the Option Seller.
- **Margin (Schedule H):** HT may call Margin in its "sole and unfettered discretion";
  the Counterparty must transfer within **6 hours** of a Margin Call Notification
  (reduced from 24 hours in the base MTA).
- **Title transfer:** all Pre-funding, Margin and purchase price transfer **full legal
  ownership** to HT — it is not held on trust, is not segregated, and HT may deal with
  it as its own. This is the single most important risk feature — see
  [[2026-04-22-ht-markets-mta-review]].

## Key Terms Snapshot

| Term | Value |
|------|-------|
| Counterparty (HT) | HT Markets (SVG) Limited, SVG reg. no. 26756 |
| Brooker contracting entity | Brooker International Company Limited (HK reg. 52931453) |
| Authorised signer (Brooker) | Varut Bulakul, Authorized Director |
| Governing law | Hong Kong; HKIAC arbitration (no interim relief) |
| Counterparty termination notice | 30 days (Counterparty) vs 1 Business Day (HT) |
| Margin payment window | 6 hours after Margin Call Notification |
| Confirmation deemed-acceptance | 4 hours |
| Default interest | EFFR + 10%, compounding daily |

## Why It Matters

This arrangement gives the CIO a venue to execute the [[dat-sell-call-strategy]]
short-call overlay and to raise fast liquidity (pledge crypto for dollar loan) under the
[[capital-sovereignty-doctrine]]. However the contract is drafted as a **title-transfer
OTC trading agreement, not a custody agreement** — the AI-assisted review
([[2026-04-22-ht-markets-mta-review]]) rated it **HIGH risk** for treasury use and
recommends splitting custody from trading.

## Related Concepts

- [[ht-markets-svg]] — the SVG counterparty entity
- [[hex-trust]] · [[hex-trust-custody-arrangement]] — the regulated custody side
- [[2026-04-22-ht-markets-mta-review]] — the contract review memo and negotiation plan
- [[dat-sell-call-strategy]] — the IC strategy this venue supports
- [[hex-trust-kyc-requirements]] — onboarding documents required before the MTA goes live

## Sources

- `Brooker Group Master Trading Agreement Template_SVG (March 2026).docx`
- `Brooker Group_MTA Supplement_Options and Margin_HT Markets (SVG) Limited(Mar 2026).docx`
- `HT_Markets_MTA_Review_Memo.docx`

## Agent Notes

Do not describe this as a "custody agreement." Treasury BTC should sit in the separate
regulated Hex Trust custody arrangement; the MTA is for the actively-traded derivatives
book only. Per the review memo, do not execute until Tier-1 redlines are agreed.
