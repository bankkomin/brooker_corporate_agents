---
title: "On-Chain Analysis Framework for Bitcoin"
type: "concept"
department: "research"
sources: ["ARKInvest_123021_Whitepaper_OnChainData.pdf", "ARK Invest x Glassnode_White Paper_Cointime Economics_Final.pdf", "Cointime Economics [DIGITAL SINGLE].pdf", "1096171.1.0 Fidelity Digital Assets - Q2 Signals Report.pdf"]
source_date: "2023-08-28"
period: "2021-2023"
related: ["bitcoin-digital-gold-thesis", "crypto-as-institutional-asset-class", "source-ark-on-chain-data-framework-2021", "source-ark-glassnode-cointime-economics-2023", "source-fidelity-q2-2023-signals"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"
coverage: "medium"
tags: ["research", "crypto", "thesis", "bitcoin", "on-chain", "valuation"]
---

# On-Chain Analysis Framework for Bitcoin

## Summary

On-chain analysis is the research discipline that treats Bitcoin's public ledger as a
fundamental dataset — analogous to financial statements for an equity. Because Bitcoin
cannot be valued by cash flows, analysts (ARK, Glassnode, Fidelity, CME) have built a
metrics framework that lets investors gauge network health, holder behaviour, and
relative valuation. ARK's 2021 white paper organises this into a three-layer pyramid;
the 2023 ARK x Glassnode collaboration extends it with "Cointime Economics," a new
unit of measurement.

## Key Metrics

**ARK three-layer pyramid (2021):**
- **Layer 1 — Network Health:** hash rate, monetary policy/issuance, active addresses,
  transaction count. For all observers.
- **Layer 2 — Buyer & Seller Behaviour:** HODL Waves, coindays destroyed, realized
  capitalization, thermo cap. For long-term holders.
- **Layer 3 — Valuation:** MVRV ratio, investor capitalization, SOPR, profit/loss
  oscillators. For active managers.

**Cointime Economics (ARK x Glassnode, Aug 2023):**
- **Coinblock** — the base unit: coins × blocks held. Weights each coin by how long it
  has been unmoved.
- **Liveliness / Vaultedness** — share of coinblocks destroyed vs. stored (0.6 / 0.4 as
  of May 2023).
- **AVIV Ratio** — a cointime-enhanced MVRV; >2.5 overbought, <0.55 oversold.
- **Cointime Price** — a time- and volume-weighted floor model ($17,568 as of May 2023).

## Historical Context

These tools matured alongside institutional adoption. Fidelity's quarterly Signals
Report operationalises them for portfolio decisions, grouping signals by time horizon
(short/mid/long) and using NUPL, MVRV Z-Score, the Puell Multiple and Reserve Risk.

## Related Concepts

- [[bitcoin-digital-gold-thesis]] — what the metrics ultimately measure
- [[crypto-as-institutional-asset-class]] — on-chain data is the class's fundamental toolkit

## Sources

- `ARKInvest_123021_Whitepaper_OnChainData.pdf` — see [[source-ark-on-chain-data-framework-2021]]
- `ARK Invest x Glassnode_White Paper_Cointime Economics_Final.pdf` / `Cointime Economics [DIGITAL SINGLE].pdf` — see [[source-ark-glassnode-cointime-economics-2023]]
- `1096171.1.0 Fidelity Digital Assets - Q2 Signals Report.pdf` — see [[source-fidelity-q2-2023-signals]]
