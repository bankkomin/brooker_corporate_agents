---
title: "CAC Monthly Data Pack — Intake Template"
type: "template"
department: "cac"
purpose: "Operational data the CAC requires each month to perform its Board-mandated functions. Finance/Treasury fills this in; it is then ingested so the CAC agent can answer with real figures instead of abstaining."
provider: "Finance / Treasury (CFO: Supane)"
cadence: "monthly (by 5th business day after month-end close)"
mandate: "Manage the Group's balance sheet, liquidity, funding structure, capital allocation priorities, and asset-liability risk exposures in accordance with Board-approved strategy, risk appetite, and treasury policies."
sources: []
related: ["cac-monthly-cfo-report", "2026-02-21-committee-governance-structure", "three-engine-model", "stay-liquid-doctrine", "investment-company-40-percent-rule"]
created: "2026-05-20"
updated: "2026-05-20"
confidence: "high"
---

# CAC Monthly Data Pack — `<YYYY-MM>`

> **How to use:** Finance/Treasury replaces every `<…>` placeholder with the
> month-end figure. Leave a cell blank only if genuinely N/A. Once filled, save a
> dated copy (e.g. `cac/trends/2026-05-data-pack.md`) so it is ingested and the
> CAC agent can cite real numbers. Reference targets/limits are pre-filled from
> Board-approved strategy — do **not** edit those columns.

**Reporting month:** `<YYYY-MM>`  ·  **Prepared by:** `<name>`  ·  **Date:** `<YYYY-MM-DD>`

### Governing basis *(the "in accordance with" anchors — confirm each month)*
- **Board-approved strategy:** Three-Engine Model + North Star 2028 (recurring income THB 500M, AUM USD 600M, D/E <0.5x). See [[three-engine-model]], [[north-star-2028]].
- **Risk appetite:** investment ratio <40% (binding 30 Jun 2026), D/E <0.5x, cost of funds <3–4%, on-chain DTV ≤25% (hard Board cap; new loans LTV <10%), ≥6 months offline-cash runway, Sovereignty Buffer ≥100 BTC, treasury native yield ≥10%. See §7.
- **Treasury policies:** Stay Liquid doctrine, melt-up/sell-down plan, Decision Rights Matrix (R-05). See [[stay-liquid-doctrine]], [[2026-02-21-committee-governance-structure]].

---

## 1. Balance Sheet Snapshot  *(mandate: balance sheet)*

| Line | This month (THB M) | Prior month | MoM Δ |
|------|--------------------|-------------|-------|
| **Total assets** | `<>` | `<>` | `<>` |
| — Current / liquid assets | `<>` | `<>` | `<>` |
| — Investments (principal + treasury) | `<>` | `<>` | `<>` |
| — Operating / other assets | `<>` | `<>` | `<>` |
| **Total liabilities** | `<>` | `<>` | `<>` |
| — Bank debt / facilities drawn | `<>` | `<>` | `<>` |
| — On-chain / structured borrowing | `<>` | `<>` | `<>` |
| — Other liabilities | `<>` | `<>` | `<>` |
| **Total equity / Net Worth** | `<>` | `<>` | `<>` |

| Key ratio | Value | Target | Status |
|-----------|-------|--------|--------|
| Debt-to-Equity (D/E) | `<>`x | <0.5x | `<>` |
| Net Worth (THB M) | `<>` | grow | `<>` |
| Investment / Total Assets | `<>`% | <40% (Jun 2026) | `<>` |

## 2. Capital Allocation Priorities  *(mandate: capital allocation priorities)*

| Bucket | Actual (THB M) | % of total assets | Target range | Variance |
|--------|----------------|-------------------|--------------|----------|
| Core operating businesses | `<>` | `<>` | per strategy | `<>` |
| Principal investments | `<>` | `<>` | ≤10% non-core | `<>` |
| VCC Platform (Engine 1, GP/seed) | `<>` | `<>` | ~15% | `<>` |
| Advisory book (Engine 2) | `<>` | `<>` | 10–30% | `<>` |
| Digital Asset Treasury (Engine 3) | `<>` | `<>` | 20–30% | `<>` |
| Strategic reserves / cash | `<>` | `<>` | ≥6mo burn | `<>` |
| **Total** | `<>` | 100% | — | — |

**Allocation vs Board priorities this month:** `<commentary on drift / rebalancing need>`

## 3. Liquidity & "Stay Liquid" Doctrine  *(mandate: liquidity)*

| Item | Value | Threshold |
|------|-------|-----------|
| Operating cash (THB M) | `<>` | — |
| Near-cash / liquid securities (THB M) | `<>` | — |
| Sovereignty Buffer (BTC) | `<>` | floor: 100 BTC |
| Monthly operating burn (THB M) | `<>` | budget ~THB 8M/mo |
| **Months of runway** | `<>` | min 6 months |

**Stress scenarios:**

| Scenario | Assumption | Result | Pass/Fail |
|----------|------------|--------|-----------|
| Crypto drawdown | −25% DAT | `<>` | `<>` |
| Cash drain | −50% cash MoM | `<>` | `<>` |
| Combined | −25% DAT + facility pull | `<>` | `<>` |

**Contingency Funding Plan status:** `<triggers active? available actions + time-to-cash>`

## 4. Funding Structure & Facilities  *(mandate: funding structure)*

| Lender | Type | Limit (THB M) | Drawn | Available | Util % | All-in rate | Maturity | Secured? | Covenant | Headroom | Renewal status |
|--------|------|---------------|-------|-----------|--------|-------------|----------|----------|----------|----------|----------------|
| SCB | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<lender covenant>` | `<>` | `<>` |
| BBL | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` |
| `<other>` | | | | | | | | | | | |
| **Aggregate** | — | `<>` | `<>` | `<>` | `<>` | wtd `<>` | — | — | — | — | — |

**Funding mix:** bank `<>`% / on-chain `<>`% / bond `<>`% / equity `<>`%
**Covenant watch:** `<any covenant within 10% of limit? any maturity <90 days without confirmed renewal?>`

## 5. Asset-Liability Risk Exposures  *(mandate: asset-liability risk exposures)*

**Tenor ladder (THB M):**

| Bucket | Assets | Liabilities | Gap |
|--------|--------|-------------|-----|
| Overnight–1m | `<>` | `<>` | `<>` |
| 1–3m | `<>` | `<>` | `<>` |
| 3–12m | `<>` | `<>` | `<>` |
| 1–5y | `<>` | `<>` | `<>` |
| >5y | `<>` | `<>` | `<>` |

- Weighted asset duration: `<>` yr · liability duration: `<>` yr · **Duration gap:** `<>` yr *(target <2.0)*
- **Refinancing next 12m:** `<amount + which facilities + renewal plan>`
- **Collateral sufficiency on secured assets:** `<>`%
- **FX exposure (USD treasury vs THB liabilities):** `<>`

## 6. On-Chain Collateral & Margin  *(Key Function 5)*

| Protocol/Venue | Collateral asset | Collateral (USD) | Borrowed (USD) | DTV % | Liquidation price | Buffer to liq | Tier |
|----------------|------------------|------------------|----------------|-------|-------------------|---------------|------|
| `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<>` | `<`<10% / 10–25% / >25%`>` |
| **Aggregate DTV** | — | `<>` | `<>` | `<>` | — | — | — |

*DTV tiers per R-05: <10% management, 10–25% committee, >25% Board.*

## 7. Risk Appetite — Limits & Escalation (shared with Risk Committee)  *(mandate: risk appetite · Key Function 6)*

| Metric | Current | Limit (appetite) | Status | Escalate to |
|--------|---------|------------------|--------|-------------|
| Investment / Total Assets | `<>` | 40% | `<>` | Board (post-Jun 2026) |
| Debt-to-Equity | `<>` | <0.5x | `<>` | Board |
| Cost of funds | `<>` | <3–4% | `<>` | CAC |
| Aggregate on-chain DTV | `<>` | ≤25% (hard cap) | `<>` | Board if >25% |
| New on-chain loan LTV | `<>` | <10% | `<>` | Committee if ≥10% |
| Treasury native yield | `<>` | ≥10% / THB 100M | `<>` | CAC |
| Liquidity runway | `<>` | ≥6mo | `<>` | CEO if <6mo |
| Sovereignty Buffer | `<>` BTC | ≥100 | `<>` | CEO if breached |

## 8. Policy Compliance Confirmation  *(mandate: Board strategy · treasury policies)*

| Policy / strategy | Compliant this month? | Note |
|-------------------|-----------------------|------|
| Board-approved strategy (Three-Engine / North Star) | `<Y/N>` | `<>` |
| Stay Liquid treasury doctrine | `<Y/N>` | `<>` |
| Melt-up / sell-down plan (40% glide path) | `<Y/N>` | `<>` |
| Decision Rights Matrix (R-05) respected | `<Y/N>` | `<>` |

## 9. Material Changes Recommended This Month  *(Key Function 7)*

| Recommendation | Amount | Required approval (per R-05 matrix) | Rationale |
|----------------|--------|-------------------------------------|-----------|
| `<>` | `<>` | `<Management / Committee / Board>` | `<>` |

---

### Data provenance
Every figure above must trace to a source (GL close, custodian statement, lender
confirmation, on-chain snapshot). Note the source per section if not the monthly
financial close.
