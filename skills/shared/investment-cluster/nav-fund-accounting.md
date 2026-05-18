---
name: nav-fund-accounting
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

This skill gives Finance, CIO, and IC agents a consistent framework for NAV calculation and fund-accounting reasoning across the investment cluster. It ensures that agents referring to BSFL, the Civetta Fund, digital-asset funds, and related vehicles use the same definitions, period-end cut-offs, and authoritative sources, and that NAV figures cited in committee discussions reconcile with the quarterly consolidated net-worth report.

## NAV Calculation

Net Asset Value (NAV) equals gross asset value less liabilities, divided by the number of units on issue.

**Step-by-step for BSFL:**

1. **Gross asset value** = MTM value of all listed equity positions + accrued dividends receivable + cash on hand for trading.
   - Listed position values come from the **BSFL Monthly report** (e.g., `BSFL Monthly 260430.xlsx`, sheet `Apr 2026`). Each position carries `Cost* (avg.)`, `Closing (MTM)`, `Value (Baht) — MTM`, and `% Change`. Sum the MTM column for all positions held at period end.
   - **Cash on hand** is recorded in the summary block (row 22 of the Apr 2026 sheet: "Cash on hand for trading").
   - **Dividend receivable** is a separate line item in the same summary block.

2. **Liabilities** — Deduct management fees accrued, redemption payables, and any other fund-level liabilities. These are recorded in the BSFL Monthly summary section.

3. **NAV** = Gross assets − Liabilities.
   - The BSFL Monthly report records `NAV pre expenses` (row 124 in Apr 2026) and final `NAV (US$)` (row 130) with a historical time series going back multiple periods.
   - `NAV (US$/share)` (row 132) provides per-unit value; as of 30 Apr 2026 this was USD 4,980.92/share.
   - `% change NAV` (row 143) is the period-on-period return.

4. **Currency conversion** — BSFL reports both THB and USD NAV. Use the `Bt/US$` rate stated in the report header (row 8) to convert. As of 30 Apr 2026 this was 32.494.

Agents must cite: `[Source: BSFL Monthly 260430.xlsx, Apr 2026 sheet | 2026-04-30]` for any NAV figure.

## Subscriptions & Redemptions

Units in BSFL and similar managed vehicles are issued and redeemed at the period-end NAV per unit (or at the NAV determined on the subscription/redemption date per the fund's constitutional documents).

**Effect on NAV calculation:**

- **Subscription**: New units issued increase both the asset base (cash received) and units on issue, leaving NAV per unit unchanged at the time of issue.
- **Redemption**: Units cancelled reduce both the asset base (cash paid out) and units on issue. The BSFL Monthly columns `Buy` (new shares acquired in the period) and `Sell` (shares sold in the period) track position-level changes; total redemptions and subscriptions at the fund level flow through to the period-end unit count.
- The BSFL Monthly column `Number of share — Beginning` vs `Ending` tracks each position's movement across the period; agents must use `Ending` as the holding for NAV purposes.

Agents should note that a large redemption in a given month will reduce NAV in absolute terms even if market prices are stable; always distinguish between NAV movement driven by price changes versus flow-driven changes.

## Fund Accounting Conventions

The following conventions apply to BSFL and to the consolidated investment vehicle accounts:

**Accrual basis** — Income (dividends, interest) is recognised when earned, not when received. The `Dividend receivable*` line in the BSFL Monthly summary reflects accrued but unpaid dividends at period end.

**Fee accruals** — Management fees and any performance fees are accrued daily against the fund's NAV. They appear as a reduction between `NAV pre expenses` and final `NAV` lines in the BSFL Monthly report.

**Unrealised gains and losses** — The `Gain (loss) — Unrealize` column in the BSFL Monthly report captures the difference between MTM value and average cost. Unrealised gains are included in the fund's NAV but are not distributable income until realised.

**Realised gains** — The `Realize` column captures P&L on positions closed during the period. These flow to the fund's income account and are distributable.

**Period-end cut-off** — Valuations use the closing price on the last trading day of the reporting period. The BSFL Monthly header records the SET Index level and Bt/US$ rate as of that specific date; agents must confirm the valuation date in the header before using figures.

**Cost basis** — `Cost* (avg.)` is the weighted-average cost per share, inclusive of brokerage commissions. The column `Cost&com. (avg.)` in the BSFL Monthly file records the fully-loaded cost basis. The `Commission` column captures the period's brokerage charges.

**Digital-asset fund conventions** — For crypto-fund holdings (OP Crypto Fund, UVM Signum Blockchain Fund, Binance Lab Fund II, Nomad Fund, Exponential Fund), the carrying value in the consolidated accounts follows the Coin Weekly Report mark for directly held tokens and the fund manager's reported NAV for externally managed vehicles. Provisions against digital-asset holdings are recorded on the Coin Weekly Report and must be reflected in period-end carrying values.

## Cross-Reference

The authoritative period-end figures for the consolidated Brooker Group investment portfolio are the **quarterly Net Worth report** and the **CIO/VCC NAV reports**.

**NET WORTH EVERY QUARTER (2025_26).xls** (sheet `2024-2025`, `O:\brooker_database\cio\portfolio\Mar\`) is the master reconciliation file. It aggregates:

| Line | Description |
|------|-------------|
| Investment in BSFL Portfolio | BSFL fund NAV at quarter end |
| Investment in Civetta Fund | Civetta fund carrying value |
| Brook Global Diversified Fund | External fund NAV |
| OP Crypto Fund | Crypto fund carrying value |
| UVM Signum Blockchain Fund | Blockchain fund NAV |
| Exponential Fund | Venture fund carrying value |
| Binance Lab Fund II / VCC FoF | Digital-asset FoF value |
| Nomad Fund | NAV |
| Trading Securities Brooker | Listed portfolio MTM |
| Trading Securities Brooker Corporate Advisory | Advisory-related holdings |
| Net worth Parent Company | Consolidated parent equity |
| Minority Interests | Minority share |
| Net worth CONSO | Total consolidated net worth |

When a cluster agent cites a fund or portfolio value, it must reconcile to the most recent quarterly Net Worth figure. If the BSFL Monthly NAV and the Net Worth file differ, the Net Worth file (being the authoritative quarterly consolidation for internal reporting purposes) takes precedence for formal reporting; the BSFL Monthly figure may be more current for intra-quarter use.

Agents must cite: `[Source: NET WORTH EVERY QUARTER (2025_26).xls | <quarter-end date>]` for any consolidated net-worth figure.
