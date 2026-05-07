---
title: "Prediction Market Pilot ($50k)"
type: "decision_log"
department: "ic"
status: "approval_required"
budget: "USD 50,000"
related: ["option-wheel-prediction-markets", "engine-framework"]
first_seen: "2026-03-19"
last_seen: "2026-03-19"
decision_owner: "ic-chair-agent"
created: "2026-05-06"
updated: "2026-05-06"
tags: ["ic", "decision", "prediction-markets", "polymarket", "chainlink", "engine-3", "approval-pending"]
---

# Prediction Market Pilot ($50k)

## Decision (pending IC approval)

Pilot a **$50,000 USDC** budget across three prediction-market strategies on Polymarket. Designated **Engine 3 — Other Innovation** ([[engine-framework]]).

## Pilot parameters *(deck slide 33)*

| Parameter | Value |
|-----------|-------|
| **Budget** | $50,000 USDC |
| Phase 1 | Crypto markets (3 strategies) |
| Phase 2 | Sports markets |
| Position size cap | $2,500 (5% of OI on small markets) |
| Daily trade slots | ~14.4 |
| **Blended projected APY** | **~2,412%** |
| Avg win rate | >85% |

## The three strategies

### A. Latency Arbitrage (20% allocation)

| Metric | Value |
|--------|-------|
| Risk profile | Medium |
| Win rate | >80% |
| Yield/slot | ~0.50% net |
| Daily trades | ~4.8 |
| Daily yield | 0.48% |
| Monthly | ~15.4% |
| APY | ~184.8% |

> Exploit **~4-second lag between Chainlink oracle updates and Polymarket resolution price**. Enter just before oracle settles, exit immediately after. Edge: speed. Requires co-location or fast API. Capped by slot availability.

### B. Delta-Neutral Market Making (50% allocation — largest)

| Metric | Value |
|--------|-------|
| Risk profile | Low-Med |
| Yield/slot | ~2.0% (low end) |
| Daily trades | ~4.8 |
| Daily yield | 4.80% |
| Monthly | ~144% |
| APY | ~4,320% |

> Post **YES and NO simultaneously** to capture the bid-ask spread on binary markets. Remain delta-neutral — profit from spread regardless of outcome. Highest daily yield. Scales with OI growth.

### C. Buy High & Settle (30% allocation)

| Metric | Value |
|--------|-------|
| Risk profile | Low |
| Win rate | >95% |
| Yield/slot | ~1.0% guaranteed |
| Daily trades | ~4.8 |
| Daily yield | 1.44% |
| Monthly | ~43.2% |
| APY | ~512% |

> Buy near-certainty YES positions (>95% probability) **slightly below $1.00**. Hold to settlement. Capture the remaining time premium as pure yield. Risk: black swan reversals — mitigated by >95% threshold filter.

## Required IC approvals

- **$50k budget release** for pilot
- Operational scope: Polymarket account, Chainlink oracle integration, trading infra (latency for strategy A)
- Risk limit: position size $2,500; total exposure ≤ $50k

## Linked

- [[option-wheel-prediction-markets]] — origin objective (Engine 3, Q2 start)
- [[engine-framework]] — Engine 3 Other Innovation Revenue line

## Source references

- IC No1 Mar 2026 deck slide 33 — Prediction Market — Pilot Strategy
- [[IC-2026-03-19]] §9 + Action & Approval

## Agent Notes

- These yield projections (2,412% APY, 4,320% on strategy B) are pilot **theoretical maximums** assuming all slots fill and OI scales — agents should ALWAYS cite "projected" and qualify with the position-size cap ($2,500) and slot-availability constraint.
- Don't quote APY without the caveats in the same sentence.
