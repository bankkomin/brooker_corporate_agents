---
title: "Algorithmic Stablecoin Death Spiral (Terra/UST)"
type: "concept"
department: "research"
sources: ["terra luna.pdf", "terra.pdf", "messari-report-crypto-theses-for-2023.pdf"]
source_date: "2022-05-18"
period: "May 2022"
related: ["source-delphi-terra-learnings-may-2022", "source-delphi-terra-luna-flash-update", "source-messari-crypto-theses-2023", "crypto-cycles-and-liquidity"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"
coverage: "high"
tags: ["research", "crypto", "thesis", "stablecoin", "risk", "terra", "post-mortem"]
---

# Algorithmic Stablecoin Death Spiral (Terra/UST)

## Summary

In May 2022 the Terra ecosystem's algorithmic stablecoin UST lost its dollar peg, wiping
out ~$40B in market cap across UST and LUNA in days — "arguably the most catastrophic
event to happen to crypto since Mt Gox." The episode crystallised a permanent risk
lesson, documented in Delphi Digital's unusually candid post-mortems: stablecoins backed
by **endogenous collateral** (a sister token that is minted/burned to defend the peg) are
structurally prone to a reflexive collapse.

## The Mechanism

A death spiral is specific to algorithmic / endogenous-collateral designs:

1. Holders redeem UST → protocol mints LUNA → LUNA supply rises, price falls.
2. Falling LUNA undermines confidence that remaining UST can be redeemed.
3. More holders redeem → more LUNA minted → vicious circle. It runs in reverse too.

The accelerant was **Anchor Protocol's fixed ~20% APY** on UST deposits. As market yields
compressed, Anchor's rate stayed fixed, ballooning UST deposits and the protocol's reserve
deficit. The immediately-callable liability was far larger than the system could defend.
Luna Foundation Guard's BTC reserves were meant to add exogenous collateral but did not
grow fast enough and fell in value alongside the broader market.

## Lessons (per Delphi)

- Unsustainable incentives bootstrap supply effectively in good times but understate the
  callable liability in bad times — "the classic algo stable mistake."
- Decentralised stablecoins that scale will likely have to start **overcollateralised**;
  purely algorithmic designs "blow up over and over again."
- Overcollateralised stablecoins (DAI) proved resilient through March 2020 and May 2022;
  centralised stablecoins (USDC, USDT) are economically safest but carry censorship risk.
- Crypto absorbed the $40B unwind without systemic contagion — evidence of "anti-fragility"
  — but the Terra narrative ("UST was the differentiator") was permanently broken.

## Historical Context

Terra collapse was the first domino of the 2022 crypto credit crisis, preceding the
failures of Celsius, Three Arrows Capital, Voyager, and ultimately FTX. Messari's 2023
Theses devoted a full "Anatomy of a Crypto Credit Crisis" chapter to the cascade.

## Related Concepts

- [[crypto-cycles-and-liquidity]] — the 2022 bear market backdrop
- [[stablecoins-digital-dollar]] — the broader stablecoin design landscape

## Sources

See [[source-delphi-terra-learnings-may-2022]] and [[source-delphi-terra-luna-flash-update]].
