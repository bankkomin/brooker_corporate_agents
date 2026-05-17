---
title: "Capital Sovereignty & Stay Liquid Doctrine"
type: "decision_log"
department: "ic"
status: "active_doctrine"
related: ["liquidity-management-policy", "investment-holding-40pct-limit", "dat-sell-call-strategy", "hex-trust", "preferred-shares-digital-credit"]
first_seen: "2026-03-19"
last_seen: "2026-05-12"
decision_owner: "ic-chair-agent"
created: "2026-05-06"
updated: "2026-05-17"
tags: ["ic", "doctrine", "liquidity", "sovereignty", "scb-recall-risk", "funding"]
---

# Capital Sovereignty & Stay Liquid Doctrine

## Doctrine

Maintain **funding sovereignty** by diversifying the firm's funding channels and pre-positioning fast-cash options to avoid forced liquidation under counterparty stress. Companion to [[engine-framework]] (offence) and [[liquidity-management-policy]] (regulation).

## Risks identified *(deck slide 31)*

1. **SCB might recall Bt 300 mn loan in July 2026.** Concurrent restriction if DAT is being sold ([[dat-sell-call-strategy]]).
2. Concentration in a single banking counterparty.
3. Need for additional fast-cash funding channels.

## Proposed funding channels (under evaluation)

| Channel | Mechanism | Status |
|---------|-----------|--------|
| **Pledge crypto for dollar loan** via [[hex-trust]] | Custodial pledge | Active — open Hex Trust custody account (Action #2 in IC approval list) |
| **Pledge crypto for dollar loan** via Aave | DeFi over-collateralised lending | Under consideration |
| **Preferred Shares as Digital Credit** | Capital structure addition — STRC-similar / financially-engineered digital credit | **In progress** — concept paper (2026 Objective #10) — see [[preferred-shares-digital-credit]] |
| **Fixed Income product** | Issue paper | Under consideration |
| **STRC** | (acronym not expanded in deck) | Under consideration |
| **SCB credit line** | Bt 240 mn available | Active backstop |

## Linkage to other decisions

- **[[dat-sell-call-strategy]]** is constrained by SCB recall: must not deplete liquidity AND lose loan facility simultaneously.
- **[[investment-holding-40pct-limit]]** rebalance plan must preserve fast-cash optionality even after sell-down.
- **[[liquidity-management-policy]]** Mar 2026 cash position (Bt 353 mn) is healthy now but vulnerable to single-counterparty event.

## Required IC approval

- **Open [[hex-trust]] Custody Account and migrate from [[fireblocks]]** — Action #2 in [[IC-2026-03-19]] Action & Approval list.

## May 2026 update *(deck slide 18)*

The doctrine was restated unchanged at the May 2026 IC meeting. Two developments:

1. The **Preferred Shares as Digital Credit** funding channel was formalised as a tracked 2026 objective (#10, "In progress") — see [[preferred-shares-digital-credit]].
2. **Hex Trust custody migration** is now reported as "almost complete; terminate Fireblocks" (deck slide 15) — the dual-custody window is closing.

## Source references

- IC No1 Mar 2026 deck slide 31 — Capital Sovereignty & Staying Liquid Doctrine
- IC No1 Mar 2026 deck slide 34 — Action & Approval (Hex Trust migration)
- [[IC-2026-03-19]] §8
- IC No2 May2026 deck slide 18 — Capital Sovereignty & Staying Liquid Doctrine
- [[IC-2026-05-12]] §9

## Agent Notes

- This doctrine is **defensive** — pair it with offensive [[engine-framework]] when answering strategy questions.
- The SCB-300mn-July recall is a **named tail risk** — surface it in any liquidity-related answer until July 2026 passes.
- Hex Trust ⇄ Fireblocks migration: until completed, the firm has dual-custody exposure; agents should note the migration window when discussing custody.
