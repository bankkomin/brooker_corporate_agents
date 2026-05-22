---
name: valuation-methodology
kind: shared-skill
cluster: investment
version: 1.0
permissions:
  mode: read_only
  data_zones: [1]
  outbound_apis: []
  read_collections: []
---

## Purpose

This skill gives Finance, CIO, and IC department agents a consistent method for valuing Brooker Group's investment holdings. Agents across all three departments must apply the same valuation hierarchy, pricing source precedence, and staleness rules so that figures cited in committee reports, NAV calculations, and financial statements are mutually consistent and traceable to authoritative sources.

## Listed Holdings

Listed equity holdings held by Brooker Group Co., Ltd. and Brooker Sukhothai Funds Limited (BSFL) are valued at **mark-to-market (MTM)** using the closing price from the Stock Exchange of Thailand (SET) on the valuation date.

The canonical source for listed holding values is the **Weekly BG report** (e.g., `Weekly BG 2026.04.30.xlsx`) for Brooker Group's proprietary portfolio and the **BSFL Monthly report** (e.g., `BSFL Monthly 260430.xlsx`) for the fund. Both files share the same column structure:

| Column | Description |
|--------|-------------|
| Share | Ticker symbol |
| Description | FOREIGN / NVDR designation |
| BB CODE | Bloomberg ticker |
| Number of share — Ending | Current holding as of period end |
| Cost* (avg.) | Average cost per share |
| Closing (MTM) | SET closing price on valuation date |
| % Change | Period return vs. cost |
| Value (Baht) — Cost* (avg.) | Position value at cost |
| Value (Baht) — MTM | Position value at market price |
| Gain (loss) — Unrealize | Unrealised P&L (MTM minus cost) |
| P/E, P/BV, Dvd. Yield | Valuation multiples and yield at current price |

The **SET Index level** and the report date are recorded in the header rows (rows 5–8 of the Weekly BG file); agents must confirm the index date matches the valuation date before using prices.

For USD-denominated positions in BSFL Monthly, use the **Bt/US$ rate** stated in row 8 (e.g., 32.494 as of 30 Apr 2026) to convert values.

Agents must cite both the report filename and its period-end date for every listed holding value. Example: `[Source: BSFL Monthly 260430.xlsx, Apr 2026 sheet | 2026-04-30]`.

## Non-Listed & Private Holdings

Non-listed and private equity positions are valued using one of three methods, applied in priority order:

1. **Comparable company / comparable transaction multiples** — Apply market multiples (P/E, EV/EBITDA, P/BV) sourced from listed peers on the SET or relevant exchange. The valuation basis must be stated explicitly.
2. **Cost / last-round price** — Where no reliable comparable exists, carry at cost or the price paid in the most recent financing round, noting the round date.
3. **Director's valuation / business plan projection** — For early-stage holdings where a formal business plan has been submitted to the Board, use the projected financials as a cross-check but do not use projected figures as the primary valuation without IC approval.

**AsianFinance (Advance Finance Public Company Limited)** is a current non-listed investment. Key valuation reference points from the BOD Business Plan (Version 7, 15 Dec 2025):

- Target return on equity: ≥ 15% p.a.
- Projected Net Interest Income (NII): THB 289.57 M (2025), 568.62 M (2026), scaling to 5,166 M (2030)
- Net Profit trajectory: THB 74.93 M (2025), near-breakeven (2026, ECL-heavy), recovering to 3,320 M (2030)
- ECL provisioning benchmark: 4% of new loan book (2026 base case)
- Loan portfolio targets: THB 15,000 M (Year 1), growing across SME, micro/nano, retail, and EV hire purchase segments

For IC and Finance agents, the **cost-basis** or **last BOD-approved valuation** is the default carrying value unless a formal revaluation has been submitted to the Investment Committee.

Agents must cite: `[Source: AsianFinance BOD BUSINESS PLAN (15 DEC 2025).pdf | 2025-12-15]`.

## Digital-Asset & Mining Positions

Digital assets and crypto-mining interests are carried at **mark-to-market in USD**, converted to THB at the BOT spot rate on the valuation date.

**Valuation inputs (Coin Weekly Report):**

The Coin Weekly Report (e.g., `2026.05.04 Coin Weekly Report (UPDATE)_.pdf`) is the authoritative mark for digital asset positions held by BICL. The report records, for each token:

| Field | Description |
|-------|-------------|
| Units | Holding as of report date |
| Total Cost (USD) | Aggregate cost basis |
| Total Closing price (USD) | Current market value at report date |
| Provision in Q2 2026 (−) | Impairment provision recognised in current quarter |
| Profit(loss) not recorded in P/L | Unrealised P&L deferred per accounting policy |
| Cost after total provision | Net carrying amount |

As of the 4 May 2026 report, the portfolio comprised BNB, BTC, KITE, MNT, MORPHO, SOL, TREE, and other tokens; total closing value was USD 47.48 M (THB 1,554 M at BOT rate 32.6063). Cumulative realised/unrealised losses since 2021 have been substantial — agents must not rely on a single period figure without reviewing the year-by-year P&L column in the report.

**Mining interests:**

The Mining Summary PPTX (`Mining Summary.pptx`) describes the operational framework. Key valuation considerations for mining positions:

- Mining equipment (Bitmain L7, L3+, S19 machines) is carried at **cost less depreciation**; warranty is typically 6 months from manufacture date.
- Mined coins transferred to the Ledger hardware wallet are valued at **spot price on the date of transfer** to the exchange; coins held in cold storage are marked at period-end spot price.
- Mining yield is measured daily via the ViaBTC pool dashboard; agents should cross-check the pool earnings report against the wallet transaction report before confirming the income figure.
- Mining sites operate at ACE (gas-power, 3.1 THB/kWh) and UBON (3.5 THB/kWh); electricity cost is a key sensitivity — a move of 0.5 THB/kWh materially affects per-coin breakeven.

Agents must cite the specific Coin Weekly Report date for any digital-asset mark. Example: `[Source: 2026.05.04 Coin Weekly Report (UPDATE)_.pdf | 2026-05-04]`.

## Valuation Date & Staleness

All valuations must carry an explicit **valuation date**. The following staleness rules apply:

| Asset class | Maximum staleness before flagging |
|-------------|----------------------------------|
| SET-listed equities | End of most recent trading week (≤ 7 calendar days) |
| Digital assets / crypto | 7 calendar days |
| NAV-based fund holdings | Most recent monthly NAV report |
| Non-listed / private | Most recent BOD- or IC-approved valuation; flag if > 6 months old |
| Mining equipment (capex) | Most recent quarterly depreciation run |

If a price or NAV is older than the thresholds above, the agent must flag it as **stale** and note the date of the last available mark before using it in any calculation or committee output.

## Citations

Agents must cite the source report and its date for every valuation figure presented. Citation format follows `skills/shared/citation-format.md`:

```
[Source: <filename> | <date>]
```

Examples:
- `[Source: Weekly BG 2026.04.30.xlsx | 2026-04-30]`
- `[Source: BSFL Monthly 260430.xlsx, Apr 2026 sheet | 2026-04-30]`
- `[Source: 2026.05.04 Coin Weekly Report (UPDATE)_.pdf | 2026-05-04]`
- `[Source: AsianFinance BOD BUSINESS PLAN (15 DEC 2025).pdf | 2025-12-15]`
- `[Source: Mining Summary.pptx | presentation date]`

Never present a valuation figure without a citation. If the source is uncertain, prefix with `"Source uncertain:"` per the citation-format skill.
