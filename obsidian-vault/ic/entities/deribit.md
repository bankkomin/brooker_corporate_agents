---
title: "Deribit"
type: "entity"
entity_type: "exchange_venue"
department: "ic"
status: "approved_venue"
related: ["dat-sell-call-strategy", "binance-bnb-otc"]
first_seen: "2026-03-19"
last_seen: "2026-03-19"
created: "2026-05-06"
updated: "2026-05-06"
tags: ["ic", "entity", "venue", "options", "crypto-derivatives"]
---

# Deribit

Crypto options exchange. Approved venue for [[dat-sell-call-strategy|BTC short-call overlay]].

## Role

- Platform for monthly OTM short call writing on BTC during the 2026 Q2 sell-down
- Provides **DVOL** (Deribit BTC implied volatility index) used for strike selection
- Provides gamma exposure data (peaks ~$75-80k for Apr/May/Jun expiries)

## Approved use *(deck slide 22 risk matrix)*

> "Use Fireblocks / Hex Trust custody and **regulated venues (Deribit, Binance Options)**." — Counterparty risk classified LOW.

## Source references

- IC No1 Mar 2026 deck slide 20 (Platform: Deribit, BTC Call Options)
- IC No1 Mar 2026 deck slide 22 (Counterparty risk: regulated venues)
- IC No1 Mar 2026 deck slide 25 (Gamma profile source: Amberdata Derivatives Analytics — Deribit BTC Options)
