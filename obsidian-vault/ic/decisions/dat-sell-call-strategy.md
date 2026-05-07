---
title: "DAT Sell + Short-Call Strategy (2026 Q2)"
type: "decision_log"
department: "ic"
status: "approval_required"
target_completion: "2026-Q2"
related: ["digital-asset-treasury-divestment", "investment-holding-40pct-limit", "binance-bnb-otc", "engine-framework", "deribit"]
first_seen: "2026-03-19"
last_seen: "2026-03-19"
decision_owner: "ic-chair-agent"
created: "2026-05-06"
updated: "2026-05-06"
tags: ["ic", "decision", "options", "dat", "twap", "short-call", "deribit", "approval-pending"]
---

# DAT Sell + Short-Call Strategy (2026 Q2)

## Decision (pending IC approval)

Combine a **TWAP sell-down** of BTC + BNB with **short call options** on Deribit to achieve [[investment-holding-limit|40% Investment / Total Assets]] compliance while preserving optionality. Target raise: **Bt ~475 mn** over 60-90 days.

## Default execution mode (use unless explicitly overridden)

When sizing this rebalance, **default to the BTC + BNB combined sell** in the deck's **29.1% / 70.9% split** (slide 16). Rationale:

1. **Already authorized.** Action #5 in the [[IC-2026-03-19]] Action & Approval list ("Sale of Digital Asset Treasury BNB and BTC up to 35% or THB 450mn") sanctions this exact combination.
2. **DAT doctrine compliance.** [[engine-framework]] requires Bt 1,000mn influence + Bt 500mn survivability floors. A BTC-only sell would consume ~93% of the BTC stack and breach the influence floor; a deck-split preserves both BTC (~30% reduction) and BNB (~36% reduction).
3. **BNB partial classification matters.** BNB OTC is 50.4% Investment-Company-classified — selling BNB requires ~2× the MTM to deliver the same numerator reduction. The deck's 70.9% BNB share already accounts for this; a naive pro-rata-by-MTM approach under-sells BNB.

### Per-coin sell sizing recipe

Given:
- `R` = required `Investment Company Baht` reduction (per [[skills/ic/portfolio]] stale-data recipe)
- `BTC_price_USD`, `BNB_price_USD` = today's prices
- `FX` = THB/USD (use most recent BOT rate)

Then:

```
BTC_tranche_bt   = 0.291 × R
BNB_tranche_bt   = 0.709 × R   ÷ 0.504    (BNB partial-classification adjustment)
BTC_to_sell      = BTC_tranche_bt   ÷ (BTC_price_USD × FX)
BNB_to_sell      = BNB_tranche_bt   ÷ (BNB_price_USD × FX)

If 3x sell+call overlay is also authorized (Action #3 active):
  multiply both BTC_to_sell and BNB_to_sell by 0.869 (saves ~13%)
```

**Worked example (test scenario, May 2026):**
- R ≈ Bt 531mn (Feb baseline + Apr token-PDF delta)
- BTC $81,000, BNB $650, FX 32.3088
- Without overlay: 59 BTC + 17,927 BNB (BNB tranche unadjusted) OR 59 BTC + 35,569 BNB (BNB tranche adjusted for 50.4% classification — likely too aggressive vs Action #5 cap)
- With 3x overlay: 51 BTC + 15,579 BNB (unadjusted) — recommended; close to deck's 461mn raise, fits Action #5 cap

### When to deviate from the deck-split default

Only deviate (e.g. BTC-only sell, or BNB-only sell) if:
1. The user explicitly requests one-sided
2. **Surface the doctrine breach** if the BTC stack would drop below the Bt 1,000mn influence floor
3. **Cross-check Action #5 cap** (Bt 450mn or 35% of stack) — overshoots require re-vote

## The "Blind Sell Problem" *(deck slide 19)*

- Current Investment Ratio: **52.8%**
- Must reach: **≤ 40%** for compliance
- Blind sell impact: **−461 MB** entire raise from holdings
- Smart way: option overlay → write OTM calls 10-15% above spot → collect 3-5% monthly premium → sell less crypto

## Strategy parameters *(slides 17-23)*

| Parameter | Value |
|-----------|-------|
| Platform | **[[deribit|Deribit]]** |
| Instrument | BTC Call Options |
| Monthly yield (1x) | 1.25% |
| Monthly yield (3x) | 3.75% |
| 3-month cumulative (3x) | ~11.4% |
| Strike rule | Spot × e^(DVOL/√12 × z), z ≈ 0.25 delta |
| Strike Apr / May / Jun | $85k / $92k / $98k |
| Max recommended leverage | **3x** (caps drawdown at ~5% portfolio if strike hit) |
| Execution | TWAP over 60-90 days + monthly OTM short call |
| Custody | [[fireblocks]] / [[hex-trust]] |

## Phase plan *(slides 17-18)*

| Phase | Action |
|-------|--------|
| **Phase 1** | Sell ~35% = $17.5mn · sell call option |
| **Phase 2** | Buy calls (increase optionality) · buy / rebalance Alts $10mn · sell call option |
| **Phase 3** | Sell remaining to hit 40% · sell call option |

## Sell-down matrix *(slide 23)*

| Strategy | BTC required @ $75k | BNB required @ $700 | Crypto saved | New ratio |
|----------|---------------------|---------------------|--------------|-----------|
| 0x baseline | 55.18 | 14,427 | 0 | <40% ✓ |
| 1x standard | 52.79 | 13,783 | 20.4 mn | <40% ✓ |
| 2x leverage | 50.36 | 13,147 | 40.7 mn | <40% ✓ |
| **3x recommended** | **47.93** | **12,508** | **61.1 mn** | **<40% ✓** |

## Risk matrix *(slide 22)*

| Severity | Risk | Mitigation |
|----------|------|------------|
| MED | Assignment Risk | BTC called away above strike at our pre-agreed happy exit |
| MED | Volatility Spike | IV spike → MTM loss on option book; manageable if held to expiry |
| LOW | Market Crash | Calls expire worthless; premium fully earned |
| LOW | Liquidity / Execution | TWAP 60-90 days; Binance OTC supports >$1mn daily |
| MED | Regulatory | Confirm with legal that option writing is within VCC mandate |
| LOW | Counterparty | [[fireblocks]] / [[hex-trust]] custody, regulated venues ([[deribit]], Binance Options) |

## Dealer gamma context *(slide 25)*

- Deribit gamma peaks ~$75-80k for all 3 expiries
- Selling calls **above** the gamma peak → dealers actively suppress rallies toward strike → improves probability of premium retention

## Required IC approvals *(slide 24, 34)*

1. **Approve 10-20% DAT sale** (formally: up to 35% or Bt 450mn per slide 34)
2. **Select scenario** — 1x (careful) / 2x (moderate) / **3x (recommended)**
3. **Authorise TWAP + Short Call mandate**
4. **Compliance check** — option writing within VCC mandate

## Linked entities

- [[binance-bnb-otc]] — BNB position being sold
- [[deribit]] — option venue
- [[fireblocks]] · [[hex-trust]] — custody (migrating Fireblocks → Hex Trust)

## Source references

- IC No1 Mar 2026 deck slides 16-25 (centrepiece of meeting)
- [[IC-2026-03-19]] §7c Sell + Call Strategy
