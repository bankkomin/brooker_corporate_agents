---
title: "IC Meeting #3 2026 — 15 June 2026 (DRAFT)"
type: "meeting_note"
department: "ic"
meeting_number: 3
meeting_year: 2026
meeting_date: "2026-06-15"
meeting_time: "10:30"
chair: "ic-chair-agent"
related_dashboard: "[[dashboard-2026-04]]"
previous_meeting: "[[IC-2026-05-12]]"
html_minutes: "data/staging/pending/ic/IC-03-2026-06-15-minutes-draft.html"
html_deck: "data/staging/pending/ic/IC-03-2026-06-15-deck-draft.html"
generated_by: "skills/ic/ic-monthly-report v1.4"
generation_date: "2026-05-29"
confidence: 0.92
tags: ["ic", "meeting", "2026", "minutes", "draft"]
created: "2026-05-29"
updated: "2026-05-29"
---

# IC Meeting #3 2026 — 15 June 2026 (DRAFT)

**Time:** 10:30 AM · 15 June 2026 (proposed)
**FX:** 32.6 THB/USD (Dashboard Apr R40) · 32.4743 (Coin Weekly 24 May BOT rate)
**Previous:** [[IC-2026-05-12]]
**Confidence:** 0.92 — highest yet (new dashboard live, macro file ingested, BNB concentration breach surfaced)

> **v1.4 changes vs v1.3 draft:**
> - Agenda renumbered 0-9 (Section 0 = Previous Minutes, Section 1 = NEW Macro)
> - Master sheet (Section 3) now shows full per-position holdings table from dashboard rows 5-31
> - **Concentration Policy now computed** — BNB OTC 28.42% > 25% cap → BREACH (prior reports incorrectly said "none")
> - Section 7 sources live from dashboard R31 (Cost / MTM / Gain%)
> - Apr Q1 ratios updated from new `O:\brooker_database\ic\Dashboard 2026.xlsx#Apr 26` (was old `cio\Dashboard Feb2026.xlsx`)

## Agenda

- 0. Previous Minutes
- 1. Macro
- 2. Liquidity Management Policy
- 3. Master sheet (full holdings + ratios + Red Flag + concentration)
- 4. Brooker Portfolio
- 5. Sukhothai
- 6. Non listed
- 7. Structured Loan
- 8. Digital Asset Division
- 9. Schedule

---

## 🟡 LEAD ITEM — Round-1 DAT execution: **PARTIALLY EXECUTED — IN PROGRESS**

| Token | Approved May 12 target | Apr 30 actual | **May 21 actual** | Δ since Apr 30 | % complete |
|---|---|---|---|---|---|
| BTC | 100 (sell 40% from 164.66) | 164.66 | **134.66** | **-30 units** | **46.4%** |
| BNB | 40,000 (sell 5% from 45,353) | 43,086.48 | **43,093.55** | +7 noise | 0% |
| SOL | 0 (sell all) | 15,380 | **9,440** | -5,940 | **38.6%** |
| Alts (KITE/MNT/MORPHO/TREE/Others) | 0 (sell all) | held | held (some net inflow) | minimal | 0% |
| **Total Bt MTM** | (raise Bt 392mn) | 1,554mn | **1,438mn** | **-Bt 116mn** | **~30%** |

**Net realised reduction since Apr 30: Bt 116mn** (USD -$3.4mn). At current pace ~6 weeks to complete — extends past 30 Jun grace deadline.

> 🚨 **Chair action #1:** confirm acceleration plan (TWAP-up / OTC block) OR accept brief post-grace breach with documented cure plan.

---

## 0. Previous Minutes — carry-forward from [[IC-2026-05-12]]

| # | Action item from May | Cap / Target | Status at June meeting |
|---|---|---|---|
| 1 | Pilot Prediction-Market Arbitrage | $50k USDC | [TBD — verify accounts opened at Kalshi/Polymarket/Opinion Lab/Pump.fun] |
| 2 | DAT Round-1 sale | Bt 392mn raise / Core Bt 1.09bn post-sale | ⏳ **~30% complete** (Bt 116mn realised, 17 days to deadline) |

**Carry-forward escalations:** MILL suspension (Q4 25 filing failure); Robinhood CEO transition + sell-company process.

## 1. Macro — synthesised from `Macro May 2026.md`

> **Source:** `O:\brooker_database\ic\Macro May 2026.md` (captured 2026-05-22). Curated synthesis of J.P. Morgan, Goldman Sachs, All-In Podcast, Macro Mondays, Jordi Visser, ECB. **The agent does not generate macro content — it ingests and renders the human-curated synthesis.**

### Executive Summary (BLUF)

- **Energy-Driven Inflation Resurgence**: Strait of Hormuz closure has pushed US headline CPI to **3.8%**, forcing the Fed to delay rate cuts to **December 2026**.
- **"SaaS Apocalypse" & AI Capex Parabola**: Hyperscalers projected to spend **>$700bn on AI infrastructure in 2026**, shifting value from legacy SaaS to physical compute, semis, and power generation.
- **Hidden Liquidity Expansion**: Despite higher official rates, dollar liquidity remains structurally loose. **ESLR reforms** let banks recycle capital aggressively in repo markets — backdoor liquidity supporting risk assets.
- **Selective Fragmentation & Détente**: Supply chains bifurcating into US- and China-aligned blocs, but the recent **Trump-Xi summit** indicates appetite for tactical economic cooperation.

### Core Theses

- **Fiscal Dominance & Stealth Liquidity** — US gov interest expenses at **$1.2 trillion/year** mean policymakers cannot afford materially higher rates. Implicit currency debasement is the unspoken policy. ESLR-driven repo recycling is the backdoor mechanism. *(Macro Mondays)*
- **AI Power Bottleneck** — primary AI constraint is no longer silicon, it's **energy**. Hyperscalers forward-buying power at premiums → FCF margin compression → debt issuance. Structural rotation: capital-light SaaS → asset-heavy industrial/energy/infra. *(Jordi Visser, J.P. Morgan, All-In)*
- **Geopolitical Fragmentation** — Hormuz handles 20% of global oil/LNG; closure exposes supply-chain fragility. Emerging markets (LatAm copper/lithium, Asia semis) capture premium pricing. *(J.P. Morgan, Goldman Sachs)*

### Consensus vs. Contrarian

- **Consensus**: inflation sticky → higher-for-longer; AI → white-collar unemployment.
- **Contrarian (Steno)**: yield curve un-inversion is **bullish**, not recessionary, in a fiscal-dominance regime.
- **Contrarian (J.P. Morgan)**: real AI casualty is **private credit** (direct lending books heavy with SaaS).
- **Contrarian (Friedberg / All-In)**: Super El Niño food shock could trigger secondary inflation wave + EM unrest in Q3-Q4.

### Cross-Asset Implications

| Asset class | Position | Rationale |
|---|---|---|
| **Equities** | OW AI physical infra (cooling, power, optical, semis); UW legacy SaaS; OW EM equities (semis dominance) | AI multiple compression on SaaS; EM low P/E + high beta |
| **Fixed Income** | UW long-duration sovereign; caution in private credit (SaaS exposure) | Sticky inflation + fiscal debasement; direct lending portfolio risk |
| **Digital Assets / Hard Money** | **Bullish BTC, Gold, Silver**; monitor DOGE as retail liquidity index | Negative real yields + currency debasement; retail proxy |
| **Commodities & FX** | Bullish energy + agriculture; CB precious-metal accumulation continues | Hormuz disruption + El Niño risk; Global South USD diversification |

### Charts to Watch

- South Korean export data (real-time semi/AI demand proxy)
- Repo market volumes (ESLR-recycled liquidity)
- Hyperscaler Capex vs FCF margin spread (Microsoft, Google, Amazon, Meta)
- Global Sea Surface Temp anomalies (El Niño / food inflation leading indicator)

> **Read-through to portfolio**: macro stance is **constructive on Engine 3 DAT (BTC, BNB)** and consistent with the DAT divestment plan reducing concentration (not de-risking entirely). Hyperscaler AI capex theme reinforces Engine 1 VCC pipeline (a16z, Pantera). El Niño + energy themes have no direct portfolio exposure but warrant monitoring.

## 2. Liquidity Management Policy

> Source: prior deck slide 17 (Apr 30 Weekly BG row 23 cash blank per known gap).

| Component | May value (Bt mn) | Source | Status |
|---|---|---|---|
| Cash Outflow (1-yr rolling) | 130 | slide 17 | unchanged |
| Cash & Equivalents | 324 | slide 17 | carry — Weekly BG gap |
| Current Stocks | 23 | slide 17 | carry |
| Current Unlocked Funds | 150 | slide 17 | carry |
| **Expected DAT sale (remaining)** | **~276** (392 − 116 realised) | computed | revised down |
| D/E Ratio | 0.29x — Low | slide 17 | carry |
| Liquidity Risk | **Low** | slide 17 | carry |

## 3. Master sheet — Apr Q1 close (FULL per-position breakdown)

> **Source:** `O:\brooker_database\ic\Dashboard 2026.xlsx#Apr 26` (the canonical v1.4 dashboard — old `cio\Dashboard Feb2026.xlsx` is obsolete). Numbers below are direct cell reads, not estimates.

### 3a. Headline ratios

| Ratio | Apr Q1 | Cap | Status | Δ vs Feb |
|---|---|---|---|---|
| **Investment / Total Asset (40% rule)** | **54.58%** | 40% | 🚨 BREACH (binding 2026-06-30) | +3.35pp from Feb 52.23% |
| Equity | 32.53% | 60% | ✓ compliant | +0.20pp |
| Fix | 0.00% | 30% | ✓ compliant | unchanged |
| Structured Loan | 28.48% | 50% | ✓ compliant | +0.67pp |
| **Digital Asset Treasury** | **65.41%** | 50% | 🚨 BREACH (widening) | +8.80pp from Feb 56.61% |

**Numerator (R32 col H):** Investment Company Baht = **Bt 1,707,313,742**
**Denominator (R38 col B):** Total Assets Q1 = **Bt 3,127,968,800**
**Total Investments (R32 col D):** Bt 3,078,214,784

### 3b. Full holdings table (per dashboard rows 5-31)

| # | Position | Cost | Price | Shares/Units | MTM (Bt) | G/L% | IC Class | IC Baht | % of Total Inv |
|---|---|---|---|---|---|---|---|---|---|
| **Listed Securities** ||||||||||
| R5 | CV | 0.47 | 0 | 10,000 | 0 | — | Yes | 0 | 0.00% |
| R6 | MILL (suspend) | 1.30 | 0.05 | 65,321,009 | 0 | -96.15% | Yes | 0 | 0.00% 🔴 |
| R7 | B-W8 | 0 | 0 | 29,987,508 | 0 | — | Yes | 0 | 0.00% |
| R8 | Wave | 0.15 | 0.02 | 1,020,308,442 | 20,406,169 | **-86.67%** | Yes | 20,406,169 | 0.66% 🔴 |
| R9 | Wave-W3 | 0.09 | 0 | 245,925,218 | 0 | -100% | Yes | 0 | 0.00% 🔴 |
| R10 | Wave-W4 | 0 | 0 | 302,030,844 | 0 | — | Yes | 0 | 0.00% |
| R11 | B | 0.19 | 0.03 | 89,962,524 | 2,698,876 | **-84.21%** | Yes | 2,698,876 | 0.09% 🔴 |
| R12 | **Listed Total** | 276.93 | | | **23,105,045** | -91.66% | | 23,105,045 | **0.75%** |
| **Non Listed Securities** ||||||||||
| R15 | Varuna | — | — | — | 100,000,000 | — | Yes | 100,000,000 | 3.25% |
| R16 | BCGT | 63.2 | — | 246,195 | 211,214 | — | — | 0 | 0.01% |
| R17 | Wave BCG | — | — | — | 0 | — | — | 0 | 0.00% |
| R18 | Robinhood | — | — | — | 78,730,605 | — | — | 0 | 2.56% |
| R19 | Advance Finance (ADFIN) | 1.48 | — | — | 185,000,000 | — | Yes | 185,000,000 | 6.01% |
| R20 | Brooker (self) | — | — | — | 387,046,863 | — | — | 0 | 12.57% |
| R21 | Sukhothai | — | — | — | 141,599,865 | — | Yes | 141,599,865 | 4.60% |
| R22 | **Total Equity Investments** | | | | **528,646,728** | | | | |
| **Digital Assets** ||||||||||
| R23 | Digital Assets (Market Value bucket) | — | — | — | 679,365,003 | — | Yes (at Cost) | 524,148,004 | **22.07%** ⚠ |
| R24 | **Binance BNB OTC** | 324 | 617 | — | **874,769,157** | — | Yes (at Cost) | 431,466,933 | **🚨 28.42% BREACH** |
| R25 | Total Tokens Market Value | | | | 1,554,134,160 | | | | |
| R26 | NFTs (Cryptopunks, Apes, ApeCoin) | 102.48 | — | — | 38,559,453 | — | Yes | 38,559,453 | 1.25% |
| R27 | Exponential Digital Age Fund | — | — | — | 9,562,372 | — | Yes | 9,562,372 | 0.31% |
| R28 | Brook Limited Partners FoF I | — | — | — | 253,872,071 | — | Yes | 253,872,071 | 8.25% |
| R29 | **Total Digital Assets Investments** | | | | **1,856,128,056** | | | | |
| **Other** ||||||||||
| R30 | Fix Income/Hybrid | — | — | — | 0 | — | — | 0 | 0.00% |
| R31 | **Structured Loan** | 1,296 | — | — | **693,440,000** | -46.49% | — | 0 | **22.53%** ⚠ |
| R32 | **TOTAL INVESTMENTS** | | | | **3,078,214,784** | | **Investment Company Baht →** | **1,707,313,742** | 100.00% |

### 3c. Red Flag positions (Gain/Loss < -25%)

Computed from dashboard col F:

| Position | Gain/Loss % | Plan |
|---|---|---|
| MILL (suspend) | **-96.15%** (MTM 0) | Impairment write-down decision; GULF partnership |
| Wave | **-86.67%** | Hold for IREC SEC approval |
| Wave-W3 | **-100%** | Expired/zero |
| B | **-84.21%** | Structured loan collateral |
| (per narrative) PACE | -100% workout | SSG Nimit |
| (per narrative) CV | -100% | K. Saithsiri loan |

### 3d. 🚨 Concentration Policy (>25% of Total Investments) — COMPUTED

**Single-position cap: 25% per [[concentration-policy]].**

| Position | MTM (Bt mn) | % of Total Inv | Status |
|---|---|---|---|
| **🚨 Binance BNB OTC (R24)** | **874.8** | **28.42%** | **BREACH — single-position cap exceeded** |
| Structured Loan (R31, aggregate of 12 loans — N/A as single-position test) | 693.4 | 22.53% | Within cap (aggregate, not single) |
| Digital Assets Market Value (R23, aggregate bucket — N/A single-position test) | 679.4 | 22.07% | Within cap (aggregate) |
| Brooker self-investment (R20) | 387.0 | 12.57% | Within cap |
| Brook LP FoF I (R28) | 253.9 | 8.25% | Within cap |

**🚨 Critical correction:** prior reports (including the May 2026 minutes) stated "Concentration: none." This was incorrect — **the dashboard has shown a BNB OTC concentration breach since at least Feb 2026** (Feb 24 share was Bt 822mn / Bt 2,925mn = 28.10%). v1.4 surfaces this for the first time. Recommend chair acknowledge prior reporting error and adopt the v1.4-computed concentration check going forward.

## 4. Brooker Portfolio — Stocks Outlook (Weekly BG 22 May)

(carry from v1.3 — Weekly BG May 22 confirmed listed positions unchanged from Apr Q1 dashboard)

| Position | Shares | MTM | Gain/Loss | Notes |
|---|---|---|---|---|
| MILL (suspend) | 65,321,009 | 0 | **-100%** | Q4 25 filing failure; impairment indicators met |
| Wave | 1,020,308,442 | 20,406,169 | **-86.67%** | Drawdown deepening |
| B | 89,962,524 | 2,698,876 | **-84.21%** | Structured loan collateral |
| CV | 10,000 | 0 | -100% | K. Saithsiri loan |
| PACE | (delisted) | 0 | -100% workout | SSG Nimit |

**Q2 2026 listed unrealized P/L to date:** -Bt 3.27mn (Weekly BG R72 col I).

## 5. Sukhothai — Apr 30 close

> Source: `O:\brooker_database\ic\BSFL Monthly 260430.xlsx#Apr 2026` rows 127-153 (May BSFL not yet published).

| Metric | Apr 30 | Source |
|---|---|---|
| NAV (US$) | $58,613,781 ≈ 58.6 mn | R131 col C |
| NAV per share | $4,980.92 | R133 col C |
| Monthly change (Apr) | +2.04% | R144 col G |
| YTD change | +7.40% | R144 col H |
| Dashboard Brooker holding (Bt) | 141.60 mn | Dashboard Apr R21 |

**Redemption status:** $500k Q2 redemption due in June.

## 6. Non listed

| Holding | Apr Q1 MTM (Bt) | Source | Status |
|---|---|---|---|
| Robinhood | 78.7 mn | Dashboard R18 | CEO exit; sell company |
| Varuna | 100 mn | R15 (100% IC) | unchanged |
| WaveBCG | 0 | R17 | flat |
| ADFIN | 185 mn | R19 (100% IC) | Varut excomm resignation ongoing |
| Brooker (self) | 387 mn | R20 | n/a |
| BCGT | 0.2 mn | R16 | likely stale per valuation skill |

## 7. Structured Loan — LIVE from Dashboard R31

> v1.4: section now sources Cost / MTM / Gain% directly from dashboard each cycle.

| Metric | Apr Q1 value | Source |
|---|---|---|
| **Cost (outstanding)** | **Bt 1,296,000,000** | Dashboard R31 col B |
| **MTM (after reserved)** | **Bt 693,440,000** | Dashboard R31 col D |
| **Gain/Loss%** | **-46.49%** | Dashboard R31 col F (E in this file) |
| Structured Loan ratio | 28.48% | Dashboard R36 col D (cap 50%) |
| Δ vs Mar Q1 | unchanged | Dashboard R31 identical across Feb/Mar/Apr |

**Per-borrower inventory:** unchanged from Mar/May 2026 per deck slide 16 — full 12-loan table:

| Borrower | Outstanding (Bt mn) | Reserved | Collateral % | Interest | Status |
|---|---|---|---|---|---|
| Kingdom Property | 4.91 | 4.91 | n/a | 10% | Apr'22 |
| Mr. Sorapoj | 408.09 | 408.09 | 0% | 3% | Sep'19 |
| Mr. Phongphan | 38.24 | 38.24 | 0% | 12% | Jan'22 |
| Moonshot | 50 | 13 | 79% | 14% | Jun'24 |
| K. Nanvarin | 20 | 17 | 22% | 14% | Aug'24 |
| K. Saithsiri (CV) | 122 | 122 | 0% | 14% | Nov'24 |
| Damri (Areeya) | 250 | — | 213% | 14% | Current |
| Barcellona (K. Chanat) | 150 | — | 206% | 14% | Current |
| Chill Space (Areeya) | 100 | — | 583% | 14% | Current |
| Wave Expo | 23.44 | — | 200% | 14% | Current |
| K. Viwat (Areeya) | 100 | — | 228% | 14% | Current |
| Purple Venture (Robinhood) | 30 | — | 0% | 3.75% | Current |
| **TOTAL** | **1,296.68** | **After-reserved 693.44** | | | |

**Areeya cluster aggregate** (Damri + Chill Space + K. Viwat) = **Bt 450mn** — concentration alert maintained per [[skills/ic/due-diligence]].

**New loans planned:** $3.75mn bridge to BTCVCC + $5mn senior debt to [[obsidian-creek-capital]] (BICL film financing, DD Q3 via Cannes).

## 8. Digital Asset Division — fresh May 21 data

(carry from v1.3 — Coin Weekly 24 May)

### 8a. Per-token holdings (May 21)

| Token | Units | MTM (USD) | MTM (Bt) | Δ vs Apr 30 | Sale target |
|---|---|---|---|---|---|
| **BNB** | 43,093.55 | 28,273,679 | **918,167,919** | +7 noise | 40,000 (sell 5%) |
| **BTC** | **134.66** | 10,365,926 | **336,626,177** | **-30 sold** | 100 (sell 40%) |
| **SOL** | **9,440** | 804,758 | 26,133,962 | **-5,940 sold** | 0 (sell all) |
| Other alts | various | ~4.8mn USD | ~157mn Bt | mixed | 0 (sell all) |
| **Total** | | **USD 44,287,129** | **Bt 1,438,193,514** | **-Bt 116mn** | Bt 392mn raise |

### 8b. Performance (deck slide 15)

MTM **$47mn → ~$44.3mn** (-7%) · This month ~-3% · YTD ~-25.6% est. · Inception USD ~+27.3% est.

### 8c. Post-sale ratio recomputation (v1.4 with new dashboard numbers)

Using updated Apr Q1 figures: IC_baht = **Bt 1,707mn**, Total Assets = Bt 3,128mn.

- Total numerator reduction (classification-adj, full Round-1): ~Bt 450mn
- Post-sale ratio = (1,707 − 450) / (3,128 + 392 − 240) = **1,257 / 3,280 = 38.32%** ← under 40% cap with 1.68pp headroom

(slightly higher than v1.3's 37.62% because the new IC_baht numerator is Bt 23mn larger)

### 8d. Custody migration

Hex Trust migration "almost complete" per May; Fireblocks termination pending.

## 9. Schedule — 2026 objectives status

(unchanged from v1.3 — see prior section)

---

## Action & Approval — June meeting

1. **Round-1 execution acceleration decision** — at current pace ~6 weeks remaining vs 17 days to grace.
2. **MILL write-down decision** — impairment indicators met.
3. **Hex Trust custody migration sign-off** — confirm complete.
4. **🚨 Acknowledge BNB OTC concentration breach** (28.42% vs 25% cap) and adopt v1.4 computed concentration check; document Round-1 sale as the cure mechanism (post-sale BNB share drops to ~23-24%).
5. **Finance liquidity refresh** — canonical cash workbook.

## Escalation flags

```json
{
  "escalation_flags": [
    {"flag": "bnb_otc_concentration_breach_long_standing", "severity": "High", "value": 0.2842, "cap": 0.25, "reason": "BNB OTC at 28.42% of Total Investments — single-position cap exceeded. Has been present since Feb 2026 but not surfaced in prior reports. Round-1 sale will cure to ~24% if BNB leg executes."},
    {"flag": "round_1_dat_pace_extends_past_grace_deadline", "severity": "Critical"},
    {"flag": "digital_asset_ratio_still_over_cap", "severity": "High", "value": 0.6541, "cap": 0.50},
    {"flag": "investment_holding_breach_17days_to_deadline", "severity": "Critical", "value": 0.5458, "cap": 0.40, "deadline": "2026-06-30"},
    {"flag": "mill_impairment_triggers_satisfied", "severity": "High"},
    {"flag": "bsfl_may_not_yet_published", "severity": "Low"},
    {"flag": "weekly_bg_cash_extraction_gap_persists", "severity": "Medium"},
    {"flag": "scb_july_recall_concurrent_dat_completion", "severity": "High"}
  ],
  "round_1_execution_status": "partially_executed_in_progress",
  "round_1_pct_complete_by_raise": 0.30,
  "round_1_days_remaining_to_grace": 17,
  "post_full_sale_ratio_estimate": 0.3832,
  "concentration_breach_bnb_otc": 0.2842,
  "confidence": 0.92
}
```

## Source files consumed

```json
{
  "source_files_consumed": [
    "O:/brooker_database/ic/Dashboard 2026.xlsx#Apr 26 (NEW canonical location — was cio/Dashboard Feb2026.xlsx)",
    "O:/brooker_database/ic/Weekly BG 2026.05.22.xlsx",
    "O:/brooker_database/ic/BSFL Monthly 260430.xlsx#Apr 2026",
    "O:/brooker_database/ic/2026.05.24 Coin Weekly Report (UPDATE)_.pdf",
    "O:/brooker_database/ic/Macro May 2026.md (NEW v1.4 source for Section 1)",
    "O:/brooker_database/ic/IC 02 meeting May2026.docx",
    "O:/brooker_database/ic/IC No2 May2026.pptx"
  ]
}
```

## Cross-references

- Concepts: [[liquidity-management-policy]] · [[red-flag-policy]] · [[concentration-policy]] · [[investment-holding-limit]] · [[engine-framework]] · [[okr-500mb-recurring-income]]
- Decisions: [[digital-asset-treasury-divestment]] · [[dat-sell-call-strategy]] · [[investment-holding-40pct-limit]] · [[sukhothai-redemption]] · [[capital-sovereignty-doctrine]]
- Previous: [[IC-2026-05-12]]
- Skills used: [[skills/ic/ic-monthly-report]] v1.4 · [[skills/ic/ic-chair-agent]] · [[skills/ic/portfolio]] · [[skills/ic/valuation]] · [[skills/ic/due-diligence]]
