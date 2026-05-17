---
title: "Option Wheel Income & Prediction Market Arbitrage (Engine 3)"
type: "decision_log"
department: "ic"
status: "active_engine_3"
related: ["binance-bnb-otc", "interactive-brokers", "kalshi", "polymarket", "opinion-lab", "pump-fun"]
first_seen: "2025-04-02"
last_seen: "2026-05-12"
decision_owner: "ic-chair-agent"
created: "2026-05-06"
updated: "2026-05-17"
tags: ["ic", "decision", "options", "prediction-markets", "engine-3", "income-strategy"]
---

# Option Wheel Income & Prediction Market Arbitrage (Engine 3)

## Decision

Replace the unsuccessful **Bitcoin arbitrage / HFT** track with two paired income strategies: **Option Wheel** and **Prediction Market Arbitrage**. Designated **Engine 3** of the firm's strategic engines (Engine 1 = [[singapore-vcc-structure]]).

## Status timeline

| Meeting | Status |
|---------|--------|
| 2025-04-02 | "Bitcoin arbitrage strategy — building track record" |
| 2026-03-19 | **Pivoted**: Option wheel + Prediction markets (R&D), formalised as Engine 3 Q2 start |
| 2026 deck Mar 2026 | **Operationalised** as two pilots requiring IC approval |
| 2026-05-12 | **Venue onboarding named** — open [[interactive-brokers]] account for CME futures/options; open [[kalshi]], [[polymarket]], [[pump-fun]], [[opinion-lab]] prediction-market accounts. Q2 start. |

## Venue onboarding (May 2026)

| Venue | Purpose |
|-------|---------|
| [[interactive-brokers]] | CME futures / options — listed-derivatives leg of the Option Wheel |
| [[kalshi]] | Regulated prediction-market exchange |
| [[polymarket]] | Crypto-native prediction market (primary pilot venue) |
| [[pump-fun]] | Solana-based venue |
| [[opinion-lab]] | Prediction-market venue |

## Operationalisation (Mar 2026 deck)

The Q2 launch is split into two distinct pilots, each with its own decision file:

1. **[[dat-sell-call-strategy]]** — short call overlay on BTC during DAT sell-down (Deribit, 1x/2x/3x scenarios; recommended 3x = ~3.75% monthly yield)
2. **[[prediction-market-pilot]]** — $50k USDC on Polymarket across 3 strategies (latency arb, delta-neutral MM, buy-high-and-settle)

This file remains as the **umbrella objective**; concrete execution lives in the two children.

## Underlying

- Option wheel against [[binance-bnb-otc]] and other token positions ([[deribit]] venue)
- Prediction markets — pilot phase ($50k seed, scaling to OI-weighted positions)

## Source references

- IC-2025-04-02 (Objectives 2025 — "Bitcoin arbitrage strategy — building track record")
- IC-2026-03-19 (Objectives 2025 #7; Objectives 2026 #6 — Engine 3 Q2 start)
- IC-2026-05-12 (Objectives 2026 #6 — "Open Interactive Brokers Account for CME futures/options; Open Kalshi, Polymarket, Pump.fun, Opinion Lab Prediction Market")
