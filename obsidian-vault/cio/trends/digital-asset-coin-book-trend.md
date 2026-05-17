---
title: "Digital Asset Coin Book — Weekly Reports Jan–Apr 2026"
type: "trend"
department: "cio"
period: "2026-01..2026-04"
sources: ["2026.01.31 Coin Weekly Report (UPDATE)_.pdf", "2026.02.28 Coin Weekly Report (UPDATE)_.pdf", "2026.03.29 Coin Weekly Report (UPDATE)_.pdf", "2026.05.04 Coin Weekly Report (UPDATE)_.pdf"]
related: ["dashboard-cio-feb-2026", "digital-asset-treasury-divestment", "dat-sell-call-strategy", "binance-bnb-otc", "investment-holding-limit"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"
coverage: "high"
tags: ["cio", "trend", "digital-asset", "coin-book", "btc", "bnb", "2026", "snapshot"]
---

# Digital Asset Coin Book — Weekly Reports Jan–Apr 2026

## Summary

A monthly series of "Coin Weekly Report (UPDATE)" PDFs tracking Brooker's digital-asset
treasury book at the token level — every coin's units, total cost, accumulated
provisions by year, closing price, MTM and unrecorded profit/loss. Four quarter-end
snapshots are available: 31 Jan, 28 Feb, 29 Mar and (Q2 update) 04 May 2026. This is the
token-level book behind the [[dashboard-cio-feb-2026]] DAT line and the input to
[[dat-sell-call-strategy]] sizing.

## Headline Series (THB)

| Date | BOT FX | Total Closing (Bt) | Inventory ex-BNB (Bt) | BNB (Bt) |
|------|-------:|-------------------:|----------------------:|---------:|
| 31 Jan 2026 | 31.2010 | 1,702.66M | 653.95M (Q1 prov −13.26M) | 1,048.71M |
| 28 Feb 2026 | 30.9390 | ~1,382.9M (per dashboard) | — | — |
| 29 Mar 2026 | 32.7615 | 1,435.81M | — | 854.82M |
| 04 May 2026 (Q2) | 32.6063 | 1,554.13M | — | 874.77M |

## Core Holdings (Stack)

The two anchor positions, stable across all four reports:

| Token | Units | Total Cost (USD) |
|-------|------:|-----------------:|
| BTC | 164.6554 | 9,399,538.57 |
| BNB | ~43,065–43,086 | ~13.19M–13.20M |

Other tracked single-name lines: KITE, MNT, MORPHO, SOL, TREE — plus an "Others" bucket
of ~100+ small tokens. The Jan report lists 108 individual tokens in full.

## Provision History (USD, cumulative)

| Year | Provision |
|------|----------:|
| 2021 | (7,987,011) |
| 2022 | (14,387,496) |
| 2023 | 8,296,779 |
| 2024 | 2,001,175 |
| 2025 | (5,384,269) |
| Q1 2026 | (424,857) → revised (1,245,082) |
| Q2 2026 | 488,336 |

Cost after total provision (the carried book value): ~USD 29.43M (Jan) → ~USD 29.27M
(May). The "Profit (loss) not recorded in P/L" line (large positive — ~USD 18–25M)
is the unrealised gain held above cost on BTC, BNB, SOL, MNT, KITE.

## Why It Matters

The coin book is the largest single driver of the **Digital Asset Treasury ratio
breach** ([[dashboard-cio-feb-2026]]) and the **40% Investment Company breach**
([[investment-holding-limit]]). The BTC + BNB stack (164.7 BTC, ~43k BNB) is the exact
inventory the [[dat-sell-call-strategy]] sell-down sizes against. The May report's
BOT rate (32.6063) and BTC/BNB units are the inputs used in the IC's Q2 rebalance
analysis.

## Linked Articles

- [[dashboard-cio-feb-2026]] — the monthly portfolio dashboard (DAT line)
- [[dat-sell-call-strategy]] — sells against this exact stack
- [[binance-bnb-otc]] — the BNB OTC position
- [[digital-asset-treasury-divestment]] — the running divestment decision

## Sources

- `2026.01.31 Coin Weekly Report (UPDATE)_.pdf`
- `2026.02.28 Coin Weekly Report (UPDATE)_.pdf`
- `2026.03.29 Coin Weekly Report (UPDATE)_.pdf`
- `2026.05.04 Coin Weekly Report (UPDATE)_.pdf`

## Agent Notes

Despite being called "weekly", the available files are quarter-end snapshots. BTC units
(164.6554) are constant across all four — no BTC has been sold yet. Use the latest
report (04 May) for current BTC/BNB stacks and FX when sizing any sell-down.
