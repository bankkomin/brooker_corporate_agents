---
title: "Failure Mode 3 — The Custody & Counterparty Breach"
type: "concept"
department: "ceo"
sources: ["BOD Khao Yai Retreat Pack 2026.docx"]
related: ["risk-pre-mortem-feb-2028", "stay-liquid-doctrine", "aave", "anchorage", "hex-trust"]
created: "2026-05-22"
updated: "2026-05-22"
confidence: "high"
coverage: "high"
tags: ["ceo", "concept", "risk", "pre-mortem", "custody", "failure-mode"]
---

# Failure Mode 3 — The Custody & Counterparty Breach

Failure mode 3 of 6 from the [[risk-pre-mortem-feb-2028|Khao Yai Risk Pre-Mortem]].

## What Happened (Hypothetical, Feb 2028)

Brooker experienced a **"Total Loss" event** in the Digital Asset Treasury.

## The Blind Spot

Management prioritised **"Yield" over "Safety"** in Engine 3. To chase yield, assets were
moved into a **re-hypothecation protocol** that suffered a smart-contract exploit — or a
"regulated" custodian turned out to have **co-mingled funds** (a repeat of the
FTX/Celsius model).

## The Consequence

**80% of the Treasury was unrecoverable.** Brooker's "institutional" reputation was
destroyed, and Engine 2 (Advisory) collapsed as clients lost faith in the firm's
technical oversight.

## Pre-Mortem Mitigation

- A strict **"No Re-hypothecation" policy** for core reserves.
- **Third-party security audits** of every on-chain protocol used for yield.
- Use **off-exchange settlement** when available.

## Related

- [[risk-pre-mortem-feb-2028]] — parent exercise
- [[stay-liquid-doctrine]] — multi-sig custody governance
- [[aave]] · [[anchorage]] · [[hex-trust]] — custody / liquidity counterparties subject to this risk

## Source References

- `BOD Khao Yai Retreat Pack 2026.docx` — Session 10, Failure Mode 3
