---
name: financial-statement-reading
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

This skill tells cluster agents how to interpret financial statements and audited reports for Brooker Group's investee and subsidiary companies. Agents applying this skill read balance sheets, P&L statements, cash-flow statements, and audit notes with consistent definitions, ratio formulas, and disclosure-reading conventions. The primary reference entity is **Brooker International Co., Ltd. (BICL)**, whose audited reports for the years ending 31 December 2024 and 31 December 2025 are held at `O:\brooker_database\finance\BICL\`.

## Statement Structure

A full-year audited report for a Brooker Group entity contains the following components. Agents should locate each before drawing conclusions:

**Balance Sheet (Statement of Financial Position)**
Reports assets, liabilities, and equity as of the period-end date. For an investment holding company such as BICL:
- *Current assets* typically include cash, short-term receivables, and current portions of loans to related parties.
- *Non-current assets* include investments in subsidiaries, associates, long-term loans to related parties, and intangible/digital assets.
- *Current liabilities* include accounts payable, accrued expenses, and short-term borrowings.
- *Non-current liabilities* include long-term borrowings and deferred tax liabilities.
- *Equity* includes paid-up capital, retained earnings, and other comprehensive income items (e.g., unrealised gains on available-for-sale investments).

**Profit and Loss (Statement of Comprehensive Income)**
Reports revenue, expenses, and net profit for the period. For BICL key line items include:
- Investment income (dividends received from subsidiaries and associate holdings)
- Gain / (loss) on disposal of investments
- Finance costs (interest on related-party loans and external borrowings)
- Administrative expenses
- Net profit / (loss) for the year
- Other comprehensive income: items not recognised in P&L (e.g., fair-value movements on equity instruments designated at FVOCI)

**Cash Flow Statement**
Operating, investing, and financing activities. For a holding company, the investing activities section (net purchases/disposals of investments, loans extended and repaid) is usually the most material.

**Notes to the Financial Statements**
The notes are integral to understanding the numbers — agents must read the relevant notes before citing any balance-sheet or P&L figure. Key notes for BICL-type entities:
- Significant accounting policies (basis of consolidation, investment classification, revenue recognition)
- Related-party transactions (loans to/from group entities — see the Loan Agreement note below)
- Investment schedule (cost and fair value of each investment by category)
- Commitments and contingencies

**Source files (BICL):**
- `BICL_AuditedReport_31Dec2025.pdf` — year ending 31 December 2025 (15 pages, scanned)
- `BICL_AuditedReport_31Dec2024.pdf` — year ending 31 December 2024 (15 pages, scanned)

Both reports are scanned-image PDFs; agents retrieving them via RAG should use the OCR-indexed version from the Qdrant collection. Always note the audit sign-off date when citing figures.

## Key Ratios

Agents should compute and cite the following ratios when assessing an investee's financial health. Use the most recent audited figures unless a more current management account is available and cited.

**Liquidity**
- *Current ratio* = Current assets ÷ Current liabilities. A ratio below 1.0 indicates potential short-term solvency pressure.
- *Quick ratio* = (Current assets − Inventories) ÷ Current liabilities. For investment holding companies without inventories, this equals the current ratio.

**Leverage**
- *Debt-to-equity (D/E)* = Total borrowings ÷ Total equity. For BICL, related-party loans (see below) must be included in "total borrowings" unless they carry equity-like subordination terms.
- *Interest coverage* = EBIT ÷ Finance costs. A ratio below 1.5× is a caution signal; below 1.0× means interest is not covered by operating earnings.

**Profitability**
- *Return on equity (ROE)* = Net profit ÷ Average equity. Brooker Group's Investment Policy sets a minimum return hurdle of the long-term Thai government bond yield; for most investments the IC targets ≥ 12% p.a. [Source: NEW INVESTMENT POLICY Feb 2024.doc | 2024-02-29]
- *Net profit margin* = Net profit ÷ Revenue.
- *Return on assets (ROA)* = Net profit ÷ Average total assets.

**Asset quality (for finance-company investees such as AsianFinance)**
- *NPL ratio* = Non-performing loans ÷ Total loans.
- *ECL coverage* = Expected Credit Loss provision ÷ Total loans. AsianFinance's 2026 plan targets ECL at ~4% of new loan book.
- *Cost/income ratio* = Operating expenses ÷ (Net interest income + other income). AsianFinance benchmarks this against Thai banks; the board target is competitive with listed peers.

All ratios must be cited with the period-end date and the source document: `[Source: BICL_AuditedReport_31Dec2025.pdf | 2025-12-31]`.

## Notes & Disclosures

The notes section often contains the most decision-relevant information. Agents must pay particular attention to:

**Related-party loan disclosures** — BICL has material inter-company loans. The key instrument is the Promissory Note No. 35 from Brooker Group Plc. to BICL, renewing PN No. 34, for USD 39.02 million (`No.35 LOAN AGREEMENT PN from BG = 39.02 USD Million (Renew PN.34).pdf`). This is a related-party loan that will appear on BICL's balance sheet as a liability to the parent. When reading the BICL balance sheet:
- Verify that the outstanding principal and accrued interest match the PN terms.
- Note the loan tenor, interest rate, and any security or covenant conditions stated in the agreement.
- Related-party loans at non-arm's-length rates require disclosure and are flagged in the independent auditor's report; agents should note any such qualification.

There is also Promissory Note No. 36 for USD 2.3 million (`No.36 LOAN AGREEMENT PN from BG = 2.3 USD Million.pdf`), which agents should include in the total related-party exposure tally.

**Contingent liabilities** — Guarantees issued by BICL on behalf of subsidiaries or by the parent on behalf of BICL should be read in the commitments and contingencies note, as they represent off-balance-sheet exposures.

**Going-concern disclosures** — If the auditor has included an emphasis-of-matter or going-concern paragraph, agents must flag this explicitly in any output that references BICL's financial health.

**Investment schedule** — The notes typically include a schedule of investments held, showing the cost and carrying value of each subsidiary/associate. This should be reconciled to the Net Worth quarterly file.

## Year-over-Year Comparison

When comparing the 2024 and 2025 audited reports for BICL, agents should:

1. **Align line items** — Confirm that accounting policies are consistent between the two periods. Any restatement or reclassification will be noted at the start of the comparative period columns.
2. **Key movements to explain** — Material changes (> 10% or > USD 1 M in absolute terms) on the following lines warrant a stated reason:
   - Total investments / investment portfolio value
   - Related-party loan balances (PN No. 34 → PN No. 35 renewal terms)
   - Net profit / (loss) year-over-year
   - Total equity and retained earnings movement
3. **Digital-asset positions** — Given the volatility of crypto holdings, the year-over-year change in the investment line for digital assets should be reconciled to the Coin Weekly Report cumulative P&L column (which shows annual figures from 2021 through Q2/2026).
4. **Audit opinion** — Note whether the 2024 and 2025 opinions are both unqualified. Any qualification, emphasis of matter, or change of auditor between years must be flagged.

Source citation pattern for year-over-year work:
```
[Source: BICL_AuditedReport_31Dec2024.pdf | 2024-12-31]; [Source: BICL_AuditedReport_31Dec2025.pdf | 2025-12-31]
```
