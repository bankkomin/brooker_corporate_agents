---
title: "Capital Sovereignty & Stay Liquid Doctrine"
type: "decision_log"
department: "ic"
status: "active_doctrine"
related: ["liquidity-management-policy", "investment-holding-40pct-limit", "dat-sell-call-strategy", "hex-trust"]
first_seen: "2026-03-19"
last_seen: "2026-03-19"
decision_owner: "ic-chair-agent"
created: "2026-05-06"
updated: "2026-05-06"
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
| **Preferred Shares** | Capital structure addition | Under consideration |
| **Fixed Income product** | Issue paper | Under consideration |
| **STRC** | (acronym not expanded in deck) | Under consideration |
| **SCB credit line** | Bt 240 mn available | Active backstop |

## Linkage to other decisions

- **[[dat-sell-call-strategy]]** is constrained by SCB recall: must not deplete liquidity AND lose loan facility simultaneously.
- **[[investment-holding-40pct-limit]]** rebalance plan must preserve fast-cash optionality even after sell-down.
- **[[liquidity-management-policy]]** Mar 2026 cash position (Bt 353 mn) is healthy now but vulnerable to single-counterparty event.

## Required IC approval

- **Open [[hex-trust]] Custody Account and migrate from [[fireblocks]]** — Action #2 in [[IC-2026-03-19]] Action & Approval list.

## Source references

- IC No1 Mar 2026 deck slide 31 — Capital Sovereignty & Staying Liquid Doctrine
- IC No1 Mar 2026 deck slide 34 — Action & Approval (Hex Trust migration)
- [[IC-2026-03-19]] §8

## Agent Notes

- This doctrine is **defensive** — pair it with offensive [[engine-framework]] when answering strategy questions.
- The SCB-300mn-July recall is a **named tail risk** — surface it in any liquidity-related answer until July 2026 passes.
- Hex Trust ⇄ Fireblocks migration: until completed, the firm has dual-custody exposure; agents should note the migration window when discussing custody.
