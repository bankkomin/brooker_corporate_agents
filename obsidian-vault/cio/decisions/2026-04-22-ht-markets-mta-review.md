---
title: "HT Markets MTA Contract Review — Negotiate Before Execution"
type: "decision_log"
department: "cio"
status: "open"
sources: ["HT_Markets_MTA_Review_Memo.docx", "Brooker Group Master Trading Agreement Template_SVG (March 2026).docx", "Brooker Group_MTA Supplement_Options and Margin_HT Markets (SVG) Limited(Mar 2026).docx"]
related: ["ht-markets-trading-arrangement", "ht-markets-svg", "hex-trust", "hex-trust-custody-arrangement", "dat-sell-call-strategy", "capital-sovereignty-doctrine"]
decision_owner: "Head of Investment (CIO)"
decision_date: "2026-04-22"
review_date: "2026-04-22"
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"
tags: ["cio", "decision", "contract-review", "counterparty-risk", "legal", "digital-asset"]
---

# HT Markets MTA Contract Review — Negotiate Before Execution

## Summary

A contract review memorandum dated **22 April 2026**, prepared for the Head of
Investment, on the [[ht-markets-trading-arrangement|HT Markets (SVG) Master Trading
Agreement]] and its Options & Margin Supplement. **Overall risk rating: HIGH** for a
treasury user. Headline decision: **do not execute** the MTA/Supplement until the Tier-1
redlines are agreed, and split the relationship into two legal tracks.

## Change Details

The memo's standing recommendations:

1. **Two-track structure** — long-term treasury digital assets go into a separate
   regulated Hex Trust custody arrangement ([[hex-trust-custody-arrangement]]); the HT
   Markets (SVG) MTA is used only for the actively-traded options/derivatives book.
2. **Do not treat HT Markets (SVG) as a custodian** — the contract creates no trust, no
   segregation, no fiduciary duty, no client-money protection.
3. **Negotiate the eight RED-severity items** before execution; obtain external Hong
   Kong counsel sign-off on the Tier-1 wording.

## Risk Register — Eight RED Items

| # | Issue | Clause |
|---|-------|--------|
| R1 | No custody — title transfer & commingling of ALL assets | 5.5, 5.12(h), Sch H §4(a) |
| R2 | Third-party sub-custody 90-day "deemed lost" loss waiver | 9.14(d) |
| R3 | Asymmetric termination — 1 Business Day for HT vs 30 days for Brooker | 3.1 |
| R4 | Unilateral close-out calculation by HT, no challenge mechanism | 3.5–3.7 |
| R5 | Margin in HT's "sole and unfettered discretion" + 6-hour window | Suppl. Sch H §2(a), §3(c) |
| R6 | Liability — no $ cap; fraud/gross-negligence/wilful-default only | 9.14(b),(c) |
| R7 | Schedule I — blanket HT discretion over adjustments / disruption events | Suppl. Sch I §1–4 |
| R8 | SVG counterparty + HK arbitration + explicit no-interim-relief bar | 9.15, 9.16 |

Twelve further YELLOW items (cure periods, one-way set-off, 4-hour Confirmation
acceptance, Force-Majeure "HT's sole view", one-way indemnity, assignment asymmetry,
data-use rights, unilateral Settlement Price, pre-funding refund discretion, 1-hour
physical settlement window, fork/airdrop entitlements, EFFR+10% default interest) are
flagged for negotiation.

## Rationale

The contracts are drafted as a **title-transfer OTC trading agreement, not a custody
agreement**. Every BTC, stablecoin or USD delivered to HT transfers full legal title;
HT may commingle and "deal with such Margin as HT's own"; on HT insolvency Brooker is an
unsecured creditor for *equivalent value*, not for return of its own assets. Combined
with wide HT discretion, very short cure windows, and SVG incorporation (no prudential
supervision), the risk profile is materially worse than a regulated exchange or custodian.

## Negotiation Plan

- **Tier 1 (must-have):** custody carve-out, segregation/return-on-demand, sub-custody
  liability, termination parity, liability cap + negligence standard, close-out mechanics,
  margin window + methodology, delete interim-relief bar, replace "sole and absolute
  discretion" in Schedule I.
- **Sequence:** lead with R3, R5, R6, R8 (most asymmetric, easiest concessions); trade
  Tier-3 items to secure Tier-1; insist on a parent guarantee if SVG incorporation is
  non-negotiable.
- **Timing:** two negotiation rounds within 5 Business Days; do not execute until items
  6.1, 6.2, 6.4, 6.5, 6.7, 6.8 are agreed.

## Impact

- **Blocks** activation of the [[dat-sell-call-strategy]] option overlay until a venue
  contract is safely executed.
- Drives adoption of the two-track structure: [[hex-trust-custody-arrangement]] for
  treasury, [[ht-markets-trading-arrangement]] for the trading book.
- Ten diligence questions issued to Hex Trust (regulatory status, parent guarantee,
  audited financials, sub-custodian list, proof-of-reserves, insurance).

## Source Evidence

- `HT_Markets_MTA_Review_Memo.docx` — 22 Apr 2026, AI-assisted review (to be confirmed by external counsel)

## Caveats

The memo is an AI-assisted review for negotiation preparation only — **not legal
advice**. All findings, risk ratings and redlines must be confirmed by qualified
external Hong Kong counsel before reliance or execution.

## Status

**OPEN** — negotiation pending; contract not executed. Awaiting Hex Trust responses to
the Section 8 diligence questions and external counsel sign-off.
