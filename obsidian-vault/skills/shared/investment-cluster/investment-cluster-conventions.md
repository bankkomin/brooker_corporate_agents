---
name: investment-cluster-conventions
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

This skill defines the shared reasoning conventions, citation style, cross-department deference rules, and escalation cues for the Finance, CIO, and Investment Committee (IC) agents that form the Brooker Group investment cluster. All three departments operate over the same underlying portfolio; consistent conventions prevent conflicting figures from reaching the committee or the board.

## Citation Style

Every factual claim about a portfolio position, NAV, ratio, or policy limit must carry an inline citation. This skill uses the format defined in `skills/shared/citation-format.md`:

```
[Source: <document-filename> | <date>]
```

For financial figures the date is the **valuation date or period-end date** of the source document, not the date the agent retrieved the file.

**Investment-cluster citation examples:**

| Claim type | Example citation |
|------------|-----------------|
| Listed equity price | `[Source: BSFL Monthly 260430.xlsx, Apr 2026 sheet | 2026-04-30]` |
| Crypto mark | `[Source: 2026.05.04 Coin Weekly Report (UPDATE)_.pdf | 2026-05-04]` |
| Consolidated net worth | `[Source: NET WORTH EVERY QUARTER (2025_26).xls, 2024-2025 sheet | <quarter-end>]` |
| Non-listed business plan figure | `[Source: AsianFinance BOD BUSINESS PLAN (15 DEC 2025).pdf | 2025-12-15]` |
| BICL audited balance sheet | `[Source: BICL_AuditedReport_31Dec2025.pdf | 2025-12-31]` |
| Related-party loan terms | `[Source: No.35 LOAN AGREEMENT PN from BG = 39.02 USD Million (Renew PN.34).pdf | <execution date>]` |
| Investment Policy limit | `[Source: NEW INVESTMENT POLICY Feb 2024.doc | 2024-02-29]` |
| Mining operations | `[Source: Mining Summary.pptx | <presentation date>]` |

Multiple sources for the same claim are separated by a semicolon inside a single citation block, per `citation-format.md`.

If an agent cannot locate a supporting source, it must prefix the claim with `"Based on general financial principles:"` and must **not** present it as a cited fact.

## Cross-Department Reasoning

The three cluster departments hold different data ownership responsibilities. When a cluster agent needs data owned by another department, it must defer to that department's authoritative source rather than interpolate or assume.

| Data type | Owning department | Deferral rule |
|-----------|------------------|---------------|
| Live portfolio marks (listed equities) | CIO | Finance and IC agents must use CIO's most recent Weekly BG / BSFL Monthly figure; do not re-price from a stale source |
| Digital-asset marks and Coin Weekly P&L | CIO / BICL | Finance and IC agents cite the Coin Weekly Report; do not adjust the mark without a CIO-issued correction |
| Consolidated net-worth reconciliation | Finance | CIO and IC agents defer to Finance's quarterly Net Worth file for any consolidated figure used in board or external reporting |
| Investment Policy limits and waivers | IC | Finance and CIO agents must check the Investment Policy before commenting on whether a position is within approved limits; IC owns all limit-breach determinations |
| BICL audited financial statements | Finance | CIO agents citing BICL's balance sheet or P&L must use the audited report; management-account drafts are not authoritative until signed by the auditor |
| Non-listed company business plans | IC / CIO jointly | Finance agents must obtain IC's current carrying value before citing a non-listed position; do not derive a value independently from the business plan projections |

When a cluster agent identifies a discrepancy between figures held by two departments (e.g., the BSFL NAV in the CIO monthly file does not match the value in the Finance quarterly net-worth report), it must flag the discrepancy explicitly rather than silently adopting one figure. Use the escalation cue format below.

## Shared Escalation Cues

The following conditions should trigger an escalation flag in any cluster agent's output, regardless of which department the agent belongs to. Escalation cues are grounded in the **Brooker Group Investment Policy (February 2024)** (`NEW INVESTMENT POLICY Feb 2024.doc`, adopted 2024-02-29 per Board resolution).

**Red-Flag Policy (Investment Policy, Equity Securities section):**
> Any individual investment with a loss greater than 25% based on cost must be reported to the Investment Committee and the Board of Directors with a rationale and plan of action.

Agents must flag a position if `(MTM − Cost) / Cost < −25%`. This applies to listed equities and digital assets; Strategic Investments are excluded.

**Concentration limit (Investment Policy):**
> No individual stock position should exceed 25% of the investment portfolio without prior approval of a convened meeting of the IC and the Board.

**NAV swing threshold:**
A period-on-period NAV change for BSFL or any managed fund exceeding ±10% should be flagged for CIO and Finance review. The BSFL Monthly `% change NAV` row provides this figure directly.

**Digital-asset provision:**
A Coin Weekly Report provision entry (column "Provision in Q2 2026 (−)") that exceeds USD 2 M for any single token, or USD 5 M in aggregate for a single quarter, warrants escalation to the IC and CFO.

**Loan covenant / related-party exposure:**
The aggregate related-party loan exposure from BICL to Brooker Group parent (PN No. 35: USD 39.02 M; PN No. 36: USD 2.3 M; total ~USD 41.3 M) is material relative to BICL's balance sheet. Any renewal, restructuring, or change in interest rate on these instruments must be flagged to Finance and IC before being reflected in BICL's accounts.

**Return hurdle breach:**
The Investment Policy requires loans to subsidiaries to earn at minimum 12% p.a. and sets a general hurdle of exceeding the long-term Thai government bond yield. If an agent computes a position's trailing return below these thresholds, it must flag the breach.

**Asset-class limit breach:**
The Investment Policy defines separate allocation limits for Equity Securities, Fixed Income, and Digital Asset Treasury (each expressed as a percentage of Total Assets; the IC may approve a 5% increase above each stated limit). Agents should check whether any proposed change in the portfolio would cause a category to exceed its approved ceiling, and flag any ceiling breach.

Escalation format:
```
ESCALATION FLAG: <condition> | [Source: <document> | <date>] | Recommend: IC review / CIO review / CFO review
```

## Governing Policy

All three cluster departments — Finance, CIO, and IC — operate under the **Brooker Group Investment Policy**, adopted by Board resolution No. 1 dated 29 February 2024 (`NEW INVESTMENT POLICY Feb 2024.doc`).

The policy organises the investable universe into four categories:

| Category | Description |
|----------|-------------|
| Equity Securities | Listed equities, equity funds, private equity, venture capital, pre-IPO, special situations, mezzanine (excluding Strategic Investments) |
| Fixed Income | Treasuries, corporate bonds, property funds, infrastructure funds, high-yield instruments, structured products |
| Digital Asset Treasury | Cryptocurrencies, tokens, SAFE notes, stablecoins (detailed policies in the Digital Asset Treasury Fund Program) |
| Loans | Loans to third parties and to subsidiaries, subject to separate collateral and return conditions |

Key governance rules agents must apply:

- IC can approve a 5% increase above the stated allocation limit for each category without Board ratification.
- New loans to third parties require security of not less than 150% of the loan amount and an identified source of repayment.
- Loan approvals to subsidiaries have tiered authority (IC / EXCO / BOD) depending on size.
- Liquidity test: listed equity positions should be liquidatable within 10 trading days on average; positions that fail this test should be noted as illiquid.

The Investment Policy is the single governing document for all cluster investment decisions. Where this or any other cluster skill conflicts with the Investment Policy, the Investment Policy prevails.
