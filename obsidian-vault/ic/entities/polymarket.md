---
title: "Polymarket"
type: "entity"
entity_type: "prediction_market_venue"
department: "ic"
status: "account_to_open"
sources: ["IC 02 meeting May2026.docx", "IC No2 May2026.pptx"]
related: ["prediction-market-pilot", "option-wheel-prediction-markets"]
first_seen: "2026-03-19"
last_seen: "2026-05-12"
created: "2026-05-17"
updated: "2026-05-17"
tags: ["ic", "entity", "prediction-market", "venue", "engine-3"]
---

# Polymarket

Crypto-native prediction-market venue — the primary platform for the **$50k prediction-market arbitrage pilot** (Engine 3).

## Role

- Polymarket is the venue assumed in the Mar 2026 [[prediction-market-pilot]] strategy design (the three strategies — latency arbitrage, delta-neutral market making, buy-high-and-settle — are all sized against Polymarket binary markets).
- The May 2026 deck Action & Approval list (slide 26) and IC minutes (Objective #6) confirm an account will be opened alongside the other pilot venues.
- Strategy A (latency arbitrage) exploits the **~4-second lag between Chainlink oracle updates and Polymarket resolution price** — see [[prediction-market-pilot]].

## Related

- [[prediction-market-pilot]] — the $50k pilot programme (Polymarket-centric)
- [[option-wheel-prediction-markets]] — Engine 3 umbrella objective
- [[kalshi]] · [[opinion-lab]] · [[pump-fun]] — fellow pilot venues

## Source references

- `IC No1 Mar 2026.pptx` slide 33 — prediction-market pilot strategies (Polymarket basis)
- `IC No2 May2026.pptx` slide 26 — "Approve and open accounts for Kalshi, Polymarket, Opinion Lab, Pump.fun"
- `IC 02 meeting May2026.docx` (Schedule for 2026 #6)
- [[IC-2026-05-12]] Action & Approval
