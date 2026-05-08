---
title: "Q2 2026 DAT Rebalance Proposal — BTC + BNB Sell-down to 40%"
type: "decision_log"
department: "ic"
status: "draft_for_review"
proposal_date: "2026-05-07"
target_completion: "2026-06-30"
related: ["dat-sell-call-strategy", "digital-asset-treasury-divestment", "investment-holding-40pct-limit", "investment-holding-limit", "binance-bnb-otc", "engine-framework", "capital-sovereignty-doctrine"]
first_seen: "2026-05-07"
last_seen: "2026-05-07"
decision_owner: "ic-chair-agent"
authored_by: "ic-chair-agent (analysis), pending IC vote"
created: "2026-05-07"
updated: "2026-05-07"
tags: ["ic", "decision", "proposal", "draft", "q2-2026", "rebalance", "btc", "bnb", "40pct-rule", "approval-pending"]
---

# Q2 2026 DAT Rebalance Proposal — BTC + BNB Sell-down to 40%

## Context

The [[investment-holding-40pct-limit|40% Investment Company / Total Assets cap]] becomes binding on **30 June 2026**. As of today (2026-05-07), the estimated ratio is **~56.3%** — driven up from the Feb 2026 dashboard's 52.23% by a 12.5% rally in the digital-asset book between Feb and late April.

This proposal sizes the **BTC + BNB sell-down** required to land the ratio at 40% by the deadline, comparing **with** and **without** the [[dat-sell-call-strategy|3x short-call option overlay]] that the IC authorized in principle on 2026-03-19 (Action #3).

## Inputs

| Input | Value | Source |
|-------|------:|--------|
| `Investment Company Baht` (Feb 2026 baseline) | Bt 1,706,260,117.84 | [[dashboard-2026-02]] row 32 col H |
| Total Assets Q4 (Estimated) | Bt 3,266,520,902.04 | [[dashboard-2026-02]] row 38 col B |
| Stale-data adjustment (Apr token-MTM delta) | + ~Bt 132 mn | Coin Weekly Report 2026-04-26 |
| Estimated current numerator | **~Bt 1,838 mn** | derived per [[skills/ic/portfolio]] stale-data recipe |
| Estimated current ratio | **~56.3%** | 1,838 / 3,266 |
| Target ratio | 40% | [[investment-holding-limit]] (binding 2026-06-30) |
| Target numerator | Bt 1,306,608,360.82 | 0.40 × 3,266,520,902 |
| **Required `Investment Company Baht` reduction** | **~Bt 531 mn** | 1,838 − 1,307 |
| BTC holdings | 164.6554 BTC | Coin Weekly Report 2026-04-26 row 2 (data 2026-03-31) |
| BNB holdings | 43,086.4760 BNB | Coin Weekly Report 2026-04-26 row 1 |
| BTC price (today) | $81,000 | user input 2026-05-07 |
| BNB price (today) | $650 | user input 2026-05-07 |
| FX | 32.3088 THB/USD | Coin Weekly Report 2026-04-26 BOT Rate |
| Bt per BTC | 2,617,013 | 81,000 × 32.3088 |
| Bt per BNB | 21,001 | 650 × 32.3088 |

## Active mandates (boundaries this proposal must respect)

Per [[IC-2026-03-19]] Action & Approval list:

| # | Action | Cap |
|---|--------|-----|
| #3 | Option trading mandate (Deribit short-call overlay) | no notional cap stated |
| **#5** | **Sale of DAT BNB and BTC** | **up to 35% per asset OR THB 450 mn total** |
| #6 | Sale of small tokens (KITE, MNT, MORPHO, SOL, TREE, etc.) | up to 100% (no cap) |

## Scenario A — WITH 3x short-call overlay *(IC-voted plan)*

Per [[dat-sell-call-strategy]] default execution mode (29.1% / 70.9% deck split, 3x leverage on Deribit):

| Side | Quantity | Bt raised |
|------|---------:|----------:|
| BTC | **51.3 BTC** | ~Bt 134.3 mn |
| BNB | **15,579 BNB** | ~Bt 327.2 mn |
| **Total cash raised** | | **~Bt 461 mn** |
| Plus 3x option premium *(3-month cumulative ~11.4% of unsold BTC+BNB underlying at strike)* | | ~Bt 70 mn |
| **Total numerator reduction** | | **~Bt 531 mn** |

**Post-sell:**
- BTC residual: **113.4 BTC** (-31% of stack — within Action #5)
- BNB residual: **27,506 BNB** (-36% of stack — marginal vs 35% cap)
- Estimated ratio: **~40.0%** ✓
- Action #5 status: **Bt 461 mn vs Bt 450 mn cap → marginal overshoot** (consistent with deck's own published plan)

## Scenario B — WITHOUT short-call overlay *(straight cash sale)*

Without premium income, the entire numerator reduction must come from raw sales. Three viable paths emerge:

### Path B-1 — BTC + BNB only, deck split *(requires Action #5 re-vote)*

| Side | Quantity | Bt raised | % of stack |
|------|---------:|----------:|-----------:|
| BTC | **59.0 BTC** | ~Bt 154.5 mn | 35.8% ⚠ (just over 35% cap) |
| BNB | **17,927 BNB** | ~Bt 376.5 mn | **41.6% ❌ over 35% cap** |
| **Total cash raised** | | **~Bt 531 mn** | |
| **Total numerator reduction** | | **~Bt 531 mn** | |

**Action #5 status:** EXCEEDS by Bt 81 mn (notional) AND by 6.6pp on BNB (per-asset). **Requires IC re-vote** to expand the cap.

### Path B-2 — Deck's FULL plan (BTC + BNB + ETH/SOL/alts) ⭐ **recommended**

The original deck plan (slide 16) included an additional **Bt 124 mn of ETH/SOL/alts sale** under Action #6 (no cap on small tokens). Today's prices and stack support a similar mix:

| Side | Quantity | Bt raised | Action authority |
|------|---------:|----------:|------------------|
| BTC | **51 BTC** | ~Bt 134 mn | Action #5 ✓ (31% of stack — within cap) |
| BNB | **15,580 BNB** | ~Bt 327 mn | Action #5 ⚠ (36% of stack — same marginal posture as deck plan) |
| ETH + SOL + KITE + MNT + MORPHO + TREE | ~50% of token stack | ~Bt 70-100 mn | Action #6 ✓ (no cap) |
| **Total cash raised** | | **~Bt 531-561 mn** | |
| **Total numerator reduction** | | **~Bt 531-561 mn** | |

**Post-sell estimate:**
- BTC residual: ~113.7 BTC
- BNB residual: ~27,506 BNB
- Tokens residual: ~50% of stack
- Estimated ratio: **~40.0% (or slightly under, providing a buffer)** ✓
- Action #5 status: marginal (same as Scenario A)
- Action #6 status: well within cap

### Path B-3 — Stay strictly under Action #5 Bt 450 mn cap *(partial fix only)*

| Side | Quantity | Bt raised |
|------|---------:|----------:|
| BTC | **50 BTC** | ~Bt 130.9 mn |
| BNB | **15,192 BNB** | ~Bt 319.1 mn |
| **Total** | | **~Bt 450 mn** (exactly Action #5 cap) |

**Post-sell ratio: ~42.2%** — still over 40%. Closes Bt 450 mn of breach but **not the 30 Jun deadline**. Phase 2 (covering the remaining ~Bt 81 mn) required before 2026-06-30 — likely via Action #6 small-tokens sale or fresh re-vote.

## Comparison (Scenario A vs B side-by-side)

| | Scenario A (3x overlay) | Scenario B-2 (full plan) | Scenario B-1 (BTC+BNB only) |
|---|---:|---:|---:|
| BTC sold | 51.3 | 51 | 59 |
| BNB sold | 15,579 | 15,580 | 17,927 |
| Tokens (alts) sold | — | ~50% of stack | — |
| Total cash raised | Bt 461 mn | Bt 531-561 mn | Bt 531 mn |
| Premium income | + Bt 70 mn | — | — |
| Total numerator reduction | Bt 531 mn | Bt 531-561 mn | Bt 531 mn |
| Action #5 status | Marginal (Bt 461 vs 450) | Marginal (Bt 461 vs 450) | **Re-vote required** |
| Action #6 status | n/a | Within cap | n/a |
| Re-vote needed | No | No | **Yes** |
| BTC residual | 113.4 | 113.7 | 105.7 |
| BNB residual | 27,506 | 27,506 | 25,160 |
| Doctrine influence floor (Bt 1,000mn) | likely OK | likely OK | tight |

## Recommendation

**Primary:** Scenario A (3x overlay, deck-split). Already IC-authorized via Actions #3 and #5. Generates Bt 70 mn of premium income that softens the cap-headroom math. Aligns with the IC-voted plan from 2026-03-19.

**Fallback (if overlay is dropped or delayed):** Scenario B-2 (full deck plan including ETH/SOL/alts under Action #6). Stays inside existing mandates without re-vote. Was already implicit in the deck slide 16 rebalance table.

**Avoid:** Scenario B-1 (BTC+BNB-only without overlay) — forces a re-vote in a tight deadline window (54 days to 2026-06-30) and offers no operational advantage over B-2.

## Required IC actions

If approving this proposal, the IC needs to confirm:

1. **Activate Action #3 (Option Trading Mandate)** — confirm the 3x Deribit short-call overlay is active for the May / June / July strikes ($85k / $92k / $98k per [[dat-sell-call-strategy]] strategy parameters)
2. **Authorise execution under Action #5** at ~Bt 461 mn raise (within cap by Bt 11 mn margin if A; otherwise B-2 stays at the same Bt 461 mn under Action #5 plus Action #6 token sales)
3. **Sequence sells before 2026-07** to avoid concurrent SCB Bt 300 mn loan recall window (per [[capital-sovereignty-doctrine]])
4. **Pre-approve Q1 2026 close-number ingestion** to convert this estimate into a confirmed plan before TWAP execution begins

## Caveats (per [[skills/ic/ic-chair-agent]] Hard Rules)

⚠ **Stale dashboard.** Numerator estimate Bt 1,838 mn is composed of Feb 2026 dashboard baseline + Apr 2026 token MTM delta. Q1 2026 close-number sourcing required before execution. Confidence ≤ 0.80.

⚠ **BNB partial Investment-Company classification (50.4% per [[skills/ic/valuation]]).** If selling BNB only proportionally reduces the Investment-Company numerator, the BNB tranche in all scenarios may need to ~2×. **Verify with accounting close before commitment.** This single classification question can swing the proposal from "achievable within mandate" to "infeasible without alts sale".

⚠ **35% per-asset cap on Action #5.** Scenarios A and B-2 both hit ~36% on BNB — marginal. The deck's own plan accepted this margin; this proposal preserves the same posture.

⚠ **Deadline tight.** 54 days from today to 2026-06-30. TWAP execution typically takes 60-90 days per [[dat-sell-call-strategy]]. The window is workable but compressed; any delay (re-vote, custody migration friction, IC schedule slip) compresses execution risk.

⚠ **Custody migration in progress.** Action #2 (open Hex Trust, migrate from Fireblocks) is still pending. Do not begin TWAP execution until at least one custody venue is confirmed live for option clearing.

## Source references

- [[IC-2026-03-19]] — Mar 2026 IC meeting; Action & Approval list
- [[dat-sell-call-strategy]] — sell+call strategy with default execution mode, sizing recipe, and worked example
- [[digital-asset-treasury-divestment]] — running parent decision
- [[investment-holding-40pct-limit]] — running 40% rebalance decision
- [[dashboard-2026-02]] — Feb 2026 baseline
- [[engine-framework]] — DAT doctrine (influence Bt 1,000mn / survivability Bt 500mn floors)
- [[capital-sovereignty-doctrine]] — SCB Bt 300mn July 2026 recall watch
- [[skills/ic/portfolio]] — stale-data recipe, BNB classification rule
- [[skills/ic/valuation]] — Investment Company classification table
- [[skills/ic/ic-chair-agent]] — approval-cap cross-check rule
- Coin Weekly Report 2026-04-26 — BTC/BNB stacks + FX + token MTM

## Output JSON (for downstream agent consumption)

```json
{
  "proposal_id": "ic-q2-2026-dat-rebalance",
  "proposal_date": "2026-05-07",
  "target_completion": "2026-06-30",
  "policy_status": {
    "ratio_today_est": 0.563,
    "cap": 0.40,
    "deadline": "2026-06-30",
    "days_remaining": 54,
    "breach_severity_pp": 16.3
  },
  "required_reduction_bt_mn": 531,
  "scenarios": {
    "A_with_3x_overlay_recommended": {
      "btc": 51.3,
      "bnb": 15579,
      "alts_bt_mn": 0,
      "raise_bt_mn": 461,
      "premium_bt_mn": 70,
      "total_numerator_reduction_bt_mn": 531,
      "btc_residual": 113.4,
      "bnb_residual": 27506,
      "post_sell_ratio_est": 0.40,
      "action_5_status": "marginal",
      "re_vote_required": false
    },
    "B2_full_deck_plan_fallback": {
      "btc": 51,
      "bnb": 15580,
      "alts_bt_mn": "70-100",
      "raise_bt_mn_range": [531, 561],
      "premium_bt_mn": 0,
      "btc_residual": 113.7,
      "bnb_residual": 27506,
      "post_sell_ratio_est": 0.40,
      "action_5_status": "marginal",
      "action_6_status": "within",
      "re_vote_required": false
    },
    "B1_btc_bnb_only_no_overlay": {
      "btc": 59,
      "bnb": 17927,
      "alts_bt_mn": 0,
      "raise_bt_mn": 531,
      "premium_bt_mn": 0,
      "btc_residual": 105.7,
      "bnb_residual": 25160,
      "post_sell_ratio_est": 0.40,
      "action_5_status": "exceeds_by_81mn_and_42pct_bnb_share",
      "re_vote_required": true
    },
    "B3_partial_within_cap": {
      "btc": 50,
      "bnb": 15192,
      "alts_bt_mn": 0,
      "raise_bt_mn": 450,
      "premium_bt_mn": 0,
      "post_sell_ratio_est": 0.422,
      "still_over_40_pct": true,
      "phase_2_required": "Bt 81 mn before 2026-06-30",
      "re_vote_required": false
    }
  },
  "caveats": [
    "stale_dashboard_q1_2026_close_required",
    "bnb_classification_50_4pct_could_double_bnb_requirement",
    "bnb_share_36pct_marginally_over_35pct_per_asset_cap_in_A_and_B2",
    "scb_300mn_recall_window_july_2026",
    "custody_migration_hex_trust_pending",
    "deadline_54_days_tight_for_twap_execution"
  ],
  "confidence": 0.74,
  "recommended_scenario": "A_with_3x_overlay_recommended",
  "fallback_scenario": "B2_full_deck_plan_fallback"
}
```

## Status

**DRAFT — pending IC review.** This proposal is not authorised to execute. It exists as a working analysis to support the next IC discussion of the [[investment-holding-40pct-limit]] running decision.

## Next steps

- [ ] Source Q1 2026 close numbers for `Investment Company Baht` and `Total Assets`
- [ ] Verify BNB OTC Investment-Company classification % at latest accounting close
- [ ] Confirm Action #3 (option mandate) operational readiness on Deribit
- [ ] Confirm at least one custody venue ([[fireblocks]] or [[hex-trust]]) live for option clearing
- [ ] Schedule IC vote: confirm Scenario A or escalate to Scenario B-2 / B-1 / B-3
- [ ] Pre-stage TWAP execution plan with venue (Binance OTC) for ~60-day window
