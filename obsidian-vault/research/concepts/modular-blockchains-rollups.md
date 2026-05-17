---
title: "Modular Blockchains and Rollup Scaling"
type: "concept"
department: "research"
sources: ["eth.pdf", "complete guid to rollups.pdf", "rollups guide.pdf", "deep dive atom 2.0.pdf"]
source_date: "2022-08-04"
period: "2022"
related: ["source-delphi-ethereum-hitchhikers-guide-2022", "source-delphi-complete-guide-to-rollups", "source-delphi-atom-2-building-the-hub-2022"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "medium"
coverage: "medium"
tags: ["research", "crypto", "thesis", "ethereum", "rollups", "scaling", "layer-2"]
---

# Modular Blockchains and Rollup Scaling

## Summary

The modular blockchain thesis (Delphi Digital, 2022) holds that blockchains scale best
by separating their core functions — execution, settlement, consensus, and data
availability (DA) — across specialised layers rather than running them all on one
"monolithic" chain. Ethereum's "rollup-centric roadmap" is the flagship: rollups handle
execution and computation, while Ethereum provides settlement and DA security. The
endgame is "centralized block production, decentralized trustless block validation, and
censorship resistance."

## Key Metrics

| Concept | Definition |
|---------|------------|
| Rollup | Executes transactions off-chain, posts compressed data + proofs to a base layer |
| Danksharding | Ethereum's DA-scaling design using data availability sampling + KZG commitments |
| Proposer-Builder Separation (PBS) | Splits block building from validation to fight MEV centralization |
| Sovereign rollup | A rollup that uses a chain (e.g. Celestia) purely for DA, not settlement |
| Modular stack | Ethereum, Celestia, Polygon Avail, Tezos as competing DA/settlement layers |

## Historical Context

These reports (mid-2022) coincided with Ethereum's Merge preparations and the rise of
Celestia as a DA-specialised competitor. The Cosmos ATOM 2.0 whitepaper applied related
ideas — Interchain Security, a USDC consumer chain, and tokenized MEV — to make the
Cosmos Hub a modular coordination layer. MEV (Maximal Extractable Value) is the central
threat the modular designs aim to neutralise.

## Related Concepts

- [[web3-ownership-thesis]] — the application layer these chains enable

## Sources

- `eth.pdf` (The Hitchhiker's Guide to Ethereum) — see [[source-delphi-ethereum-hitchhikers-guide-2022]]
- `complete guid to rollups.pdf` / `rollups guide.pdf` (duplicate documents) — see [[source-delphi-complete-guide-to-rollups]]
- `deep dive atom 2.0.pdf` — see [[source-delphi-atom-2-building-the-hub-2022]]
