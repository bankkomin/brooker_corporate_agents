---
title: "Ethereum Scaling: Rollups and the Modular Stack"
type: "concept"
department: "research"
sources: ["rollups guide.pdf", "state-of-crypto-2022_a16z-crypto.pdf"]
source_date: "2022-08-04"
period: "2022"
related: ["source-delphi-complete-guide-to-rollups", "source-a16z-state-of-crypto-2022", "source-messari-state-of-bnb-chain-q1-2023", "web3-ownership-thesis"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "medium"
coverage: "medium"
tags: ["research", "crypto", "thesis", "ethereum", "rollups", "layer-2", "infrastructure"]
---

# Ethereum Scaling: Rollups and the Modular Stack

## Summary

A technical-infrastructure thesis recurring in the Delphi and a16z material: Ethereum
scales not by enlarging the base layer but by moving execution off-chain into **rollups**,
while the base layer specialises in settlement and data availability — the "modular
blockchain" stack.

## Core Concepts

- **Layer 2 / rollups** are separate blockchains that extend the base layer and inherit
  its security. Two families:
  - **Optimistic rollups** — assume transactions valid, challengeable for ~1 week; more
    production-ready, easier to program (most popular L2 tech in 2022).
  - **Zero-knowledge (ZK) rollups** — validity proven cryptographically off-chain;
    instant L1 finality, harder to program, improving fast.
- **Modular stack** splits blockchain tasks into separate components: Data Availability
  (DA), settlement, execution, consensus. Ethereum and Celestia (plus Polygon Avail,
  Tezos) compete on these layers.
- **EIP-4844 (proto-danksharding)** is identified as the key upgrade to make rollups
  cheap for users.
- L2 rollups compete hard to drive transaction fees down and already contribute a
  meaningful share of Ethereum fees.

## Why It Matters

The thesis underpins Ethereum's claim to remain the dominant smart-contract platform
despite higher base-layer fees than rivals: scaling is delegated to a competitive L2
ecosystem rather than sacrificing decentralisation. BNB Chain adopted a comparable
roadmap (ZK + optimistic rollups, see [[source-messari-state-of-bnb-chain-q1-2023]]).

## Related Concepts

- [[web3-ownership-thesis]] — the application layer rollups serve
- [[crypto-cycles-and-liquidity]] — infrastructure build-out is a "winter" activity

## Sources

See [[source-delphi-complete-guide-to-rollups]] and [[source-a16z-state-of-crypto-2022]].
