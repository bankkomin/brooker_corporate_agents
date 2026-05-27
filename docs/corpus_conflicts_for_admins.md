# Corpus conflicts blocking 100% use-case accuracy

_Generated 2026-05-26 by scripts/corpus_conflict_audit.py_

Each section is a failing use-case test where the agent abstained or answered wrong because the retrieval found a stale / competing chunk before (or instead of) the canonical one. Items below need data-owner review — either delete the stale chunk, update its source label, or re-ingest the canonical version with a header that boosts findability.

## CEO — North Star AUM target

**Query:** `what is the institutional AUM North Star target?`
**Canonical answer:** USD 600M institutional AUM (North Star 2028)

_Why this fails today:_ The North Star 2028 target is USD 600M. Multiple stale chunks title themselves 'AUM Target' with smaller / interim figures ($500 mn, $50-100 mn) which the LLM picks up and quotes wrongly.

### Conflicting chunks in `ceo_docs` (1 found)

- **score `0.570`** | source: `brooker_database`
  > 'AUM Target: $500 mn.'

### Conflicting chunks in `shared_policies` (1 found)

- **score `0.504`** | source: `bulk_ingest`
  > 'form\nTarget AuM: $100M+\nOur Journey...'

### Canonical chunks already in `ceo_knowledge` (3 found — boost these)
- source: `obsidian_vault`
  > 'on (placement agents) | [[eastbound]] (Singapore), [[finex]] (Hong Kong) — primary agents for the global USD 600M AUM target |\n| Custody & on-chain liquidity | Aave, [[hex-trust]], Anchorage |\n| Branding & cultural capital | Film-financing funds, digital IP (CryptoPunks) merchand'
- source: `obsidian_vault`
  > '26-05-17"\nupdated: "2026-05-17"\ntags: ["ceo", "decision", "partners", "counterparty", "khao-yai", "resolution"]\n---\n\n# R-06 — Ratification of the Strategic Partner Map\n\n## Decision\n\nThe Board ratifies the engagement of the critical counterparties that form the "rails" of\nBrooker\''
- source: `obsidian_vault`
  > 'k, and bond funding (see [[stay-liquid-doctrine]]) |\n| Cashflow | The Fee-Income Flywheel — pooling accredited investors into the licensed VCC platform |\n\n## Key Metrics / Thresholds — 2028 Targets\n\n| Metric | 2028 Target |\n|--------|-------------|\n| Recurring income | THB 500M a'

### Canonical chunks already in `ceo_docs` (4 found — boost these)
- source: `obsidian_vault`
  > ' | Placement agent |\n| Location | Singapore |\n| Client base | ~500 clients across Asia and Europe |\n| Mandate | Help raise toward the global $60M VCC fundraising goal (part of the USD 600M AUM target) |\n\n## Relationships\n\n- **[[finex]]** — co-placement agent (Hong Kong)\n- **[[bro'
- source: `obsidian_vault`
  > 'me target: THB 500M/yr by Q4 2026\n- AUM target: USD 600M by 2028\n- Sovereignty Buffer: 100 BTC\n- 2026 budget: ~THB 95.7M operating + USD 21M strategic seeding\n\n## Follow-Up\n\nQuarterly OKR review at Board level; next strategic retreat at Khao Yai (annual).'
- source: `brooker_database`
  > 'Summary: The North Star defines Brooker as an Institutional Innovation Machine. We will reach THB 500M in recurring cashflow and USD 600M in AUM by mastering three pillars: Regulatory Integrity, Liquidity Sovereignty, and Product Scalability.'

---

## CEO — North Star recurring income

**Query:** `what is the North Star 2028 recurring income target?`
**Canonical answer:** THB 500M recurring income (North Star 2028)

_Why this fails today:_ North Star recurring-income target is THB 500M. Watch for chunks that cite the THB 100M treasury-yield sub-target as if it were the headline recurring-income figure.

_No conflicting chunks detected in expected collections — this may be a pure paraphrase-gap rather than a corpus issue._

### Canonical chunks already in `ceo_knowledge` (5 found — boost these)
- source: `obsidian_vault`
  > ' VCC platform |\n| Treasury growth | Maintain high-growth digital-asset exposure; grow balance sheet toward THB 4bn (from ~THB 1bn) |\n| Leverage | D/E below 0.5x |\n| Market narrative | Share price reflecting an earnings multiple on fees, not a discount to NAV |\n\n### THB 500M Recur'
- source: `obsidian_vault`
  > '-------------|\n| OKR 1 — Revenue Transformation | Shift the valuation driver to recurring fee income | THB 500M annualised run-rate by Q4 2026; launch & seed 2 VCC funds (AUM $50M + $100M); ≥3 advisory mandates |\n| OKR 2 — Structural & Regulatory Re-alignment | Return to 40%-rule'
- source: `obsidian_vault`
  > ' "2026-05-17"\ntags: ["ceo", "decision", "okr", "targets", "khao-yai", "resolution"]\n---\n\n# R-07 — Approval of the 2026 12-Month OKRs\n\n## Decision\n\nThe Board adopts the 2026 OKR framework as the primary measure of management performance —\nfive objectives laddering up to the [[nort'

### Canonical chunks already in `ceo_docs` (5 found — boost these)
- source: `brooker_database`
  > 'Achieve an annualized income run-rate of THB 500 million by Q4 2026.'
- source: `obsidian_vault`
  > 'me target: THB 500M/yr by Q4 2026\n- AUM target: USD 600M by 2028\n- Sovereignty Buffer: 100 BTC\n- 2026 budget: ~THB 95.7M operating + USD 21M strategic seeding\n\n## Follow-Up\n\nQuarterly OKR review at Board level; next strategic retreat at Khao Yai (annual).'
- source: `obsidian_vault`
  > '(VCC subfund) |\n| Target return | ~14% p.a., no negative months target |\n| AUM target | $500M (USD 250M used in the THB 500M income calculation) |\n| Economics | 0.5–0.8% advisor fee + 10% performance fee |\n| Redemptions | Quarterly |\n| Internal seed | $10M priority allocation, st'

---

## VCC — FoF I hard cap

**Query:** `what is the hard cap on Brook LP FoF I?`
**Canonical answer:** Hard cap US$150M (Supplement Key Commercial Terms)

_Why this fails today:_ Supplement S.4.1 sets hard cap at US$150M. Older/marketing chunks mention the US$100M target or US$50M expected-launch figure — the LLM picks those when the canonical chunk isn't ranked first.

### Conflicting chunks in `vcc_knowledge` (1 found)

- **score `0.432`** | source: `obsidian_vault`
  > ' VC, AUM <US$100M: 6.30x median MOIC / 78% median IRR vs >US$400M established at\n5.10x / 65% (deck slide 68).\n\n## Related\n\n- [[brook-lp-fof-strategy]] — the strategy this data underpins\n\n## Source References\n\n- `Brook Limited Partners FoF_I_Full_Deck_HemrajVersion.pptx` — slides '

---

## VCC — FoF I management fee

**Query:** `what is the management fee on Brook LP FoF I?`
**Canonical answer:** 1.5% p.a. Management Fee (Supplement)

_Why this fails today:_ 1.5% is the FoF I Management Fee. Competing chunks describe the Ternary TSA 'residual' fee mechanic (which is the BICL technical services fee, NOT the LP-facing mgmt fee) or the Brook Turtle deck 1.0% figure. Easy LLM mix-up.

### Conflicting chunks in `vcc_knowledge` (1 found)

- **score `0.550`** | source: `obsidian_vault`
  > "anager of important developments affecting the Fund.\n\nAll recommendations are **non-binding**; all investment decisions remain solely the\nManager's responsibility.\n\n## Fee Mechanism — Technical Services Fee\n\n- The Technical Services Fee is **residual Management Fees**: the Manage"

### Conflicting chunks in `vcc_docs` (2 found)

- **score `0.563`** | source: `brooker_database`
  > 'ultant residual Management Fees, which is the amount after deducting (1) \nTernary Fees (as agreed on letter of engagement signed dated 19 June 2025), (2) \nportfolio manager salary, and (3) any expenses incurred by the Manager, out of the \nmanagement fees received from Brook Techn'
- **score `0.517`** | source: `brooker_database`
  > 'dance of doubt, \nshould any additional sub-fund(s) be launched under Brook Technology Capital VCC \nin the future, the same fee structure and deduction methodology shall apply to the \nmanagement fees received from such sub-fund(s), unless otherwise agreed in writing \nby the partie'

---

## Legal — PE mitigation

**Query:** `what is the most actionable mitigation for FOF place-of-effective-management risk?`
**Canonical answer:** Assign FOF bank-account signing authority to a non-Thai-resident, exercise outside Thailand

_Why this fails today:_ Timblick opinion (para 4(d)/4(e)) names ONE actionable mitigation: non-Thai-resident signer, offshore signing. The retrieved chunks are about the GENERAL PE doctrine (5(2)(a)/5(4)(e)) and reverse-solicitation — adjacent but not the mitigation itself.

### Conflicting chunks in `legal_knowledge` (1 found)

- **score `0.468`** | source: `obsidian_vault`
  > ' | **Low risk** if strict reverse-solicitation limits observed | [[reverse-solicitation-thai-sec]] |\n| Business Development Officer | **Low risk** if conducted via a licensed Thai intermediary with SEC registration | [[bdo-venture-capital-events-thai-intermediary]] |\n| IR & BDO a'

### Conflicting chunks in `legal_docs` (2 found)

- **score `0.351`** | source: `brooker_database`
  > 'The activities of the Head of Investor Relations of BROOK which involve engaging in reverse solicitation activities in respect of FOF in Thailand and making referrals to Ternary are considered to be presented a relatively low risk of being regarded as an offering of securities in'
- **score `0.320`** | source: `brooker_database`
  > 'the Head of Investor Relations of BROOK may engage in reverse solicitation activities in respect of FOF (as defined below) in Thailand and make referrals to Ternary (as defined below); and'

---

## CIO — BTC holdings

**Query:** `how many BTC do we hold per the coin book?`
**Canonical answer:** 164.6554 BTC (coin book Jan/Feb/Mar/Apr 2026, units constant)

_Why this fails today:_ Coin book holds 164.6554 BTC (cost USD 9.4M). 'Sovereignty Buffer: 100 BTC' is the FLOOR, not the holding. LLM regularly conflates them.

_No conflicting chunks detected in expected collections — this may be a pure paraphrase-gap rather than a corpus issue._

### Canonical chunks already in `cio_knowledge` (3 found — boost these)
- source: `obsidian_vault`
  > 't this exact stack\n- [[binance-bnb-otc]] — the BNB OTC position\n- [[digital-asset-treasury-divestment]] — the running divestment decision\n\n## Sources\n\n- `2026.01.31 Coin Weekly Report (UPDATE)_.pdf`\n- `2026.02.28 Coin Weekly Report (UPDATE)_.pdf`\n- `2026.03.29 Coin Weekly Report '
- source: `obsidian_vault`
  > '04 May 2026 (Q2) | 32.6063 | 1,554.13M | — | 874.77M |\n\n## Core Holdings (Stack)\n\nThe two anchor positions, stable across all four reports:\n\n| Token | Units | Total Cost (USD) |\n|-------|------:|-----------------:|\n| BTC | 164.6554 | 9,399,538.57 |\n| BNB | ~43,065–43,086 | ~13.19'
- source: `obsidian_vault`
  > 'ekly", the available files are quarter-end snapshots. BTC units\n(164.6554) are constant across all four — no BTC has been sold yet. Use the latest\nreport (04 May) for current BTC/BNB stacks and FX when sizing any sell-down.'

### Canonical chunks already in `cio_docs` (5 found — boost these)
- source: `brooker_database`
  > '00\n              \n0.1342\n5,395\n                          \n(8,611)\n                      \n-\n                             \n5,395\n                           \n19\nBTC\nBitcoin\n164.6554\n                   \n9,399,538.5700\n         \n(1,888,360.23)\n          \n(4,786,412.19)\n          \n4,23'
- source: `brooker_database`
  > '       \n-\n                         \n13,626,049\n           \n13,202,177\n            \n874,769,157\n      \n-\n                      \n444,295,027\n                 \n430,474,130\n               \n2\nBTC\n164.6554\n                                 \n9,399,538.5700\n                   \n13,144,097\n'
- source: `brooker_database`
  > '       \n-\n                         \n12,894,674\n           \n13,197,515\n            \n854,819,242\n      \n-\n                      \n422,448,864\n                 \n432,370,379\n               \n2\nBTC\n164.6554\n                                 \n9,399,538.5700\n                   \n10,859,834\n'

---

## IC — 40% rule numerator column

**Query:** `which dashboard column is the numerator for the 40 percent Investment Company rule?`
**Canonical answer:** 'Investment Company Baht' column H (row 32) of [[dashboard-2026-02]]

_Why this fails today:_ Hard Rule in skills/ic: numerator is 'Investment Company Baht' (col H), NOT 'Total Investments' (col B — yields wrong answer, off by 2× for BNB OTC). One earlier LLM run fabricated 'aggregate Management Fee paid' as the numerator. The canonical chunk likely needs to be boosted with explicit 'numerator' keyword in its header.

### Conflicting chunks in `ic_knowledge` (4 found)

- **score `0.447`** | source: `obsidian_vault`
  > 'f the reduction cannot be executed inside one quarter.\n\n## Related Concepts\n\n- [[red-flag-policy]] — companion -25% loss test\n- [[investment-holding-limit]] — 40% Investment / Total Assets cap\n\n## Source References\n\n- IC Meeting #1 2025 (2025-01-23) — "CONCENTRATION >25% POLICY" '
- **score `0.447`** | source: `obsidian_vault`
  > 'not exceed **25% of the total investment portfolio** measured at MTM. Concentration breaches and Red Flag positions are tracked as separate sub-sections of the Master Sheet at every IC meeting.\n\n## Definition\n\n```\nPosition MTM / Total Investment Portfolio MTM  >  25%   →  CONCENT'
- **score `0.437`** | source: `obsidian_vault`
  > "imit\n\n## Summary\n\nInvestments may not exceed **40% of Total Assets**. The firm has been in a **2-year grace period** carrying excess investment exposure with the regulator's acknowledgement; the grace period **ends 30 June 2026**, after which the ratio must be brought below 40% v"
- **score `0.418`** | source: `obsidian_vault`
  > '026-03-19) — "CONCENTRATION >25% POLICY: none"\n\n## Agent Notes\n\n- Read `Total Investments` (Dashboard row 32) and divide each holding MTM by it.\n- A position that is BOTH Red Flag AND concentration-breaching triggers a **Critical** escalation.\n- "none" is a valid status — agents '

### Canonical chunks already in `ic_knowledge` (5 found — boost these)
- source: `obsidian_vault`
  > 'binding 2026-06-30) |\n| Target numerator | Bt 1,306,608,360.82 | 0.40 × 3,266,520,902 |\n| **Required `Investment Company Baht` reduction** | **~Bt 531 mn** | 1,838 − 1,307 |\n| BTC holdings | 164.6554 BTC | Coin Weekly Report 2026-04-26 row 2 (data 2026-03-31) |\n| BNB holdings | 4'
- source: `obsidian_vault`
  > 'Estimated) | Bt 3,266,520,902.04 | [[dashboard-2026-02]] row 38 col B |\n| Stale-data adjustment (Apr token-MTM delta) | + ~Bt 132 mn | Coin Weekly Report 2026-04-26 |\n| Estimated current numerator | **~Bt 1,838 mn** | derived per [[skills/ic/portfolio]] stale-data recipe |\n| Esti'
- source: `obsidian_vault`
  > 'e ratio at 40% by the deadline, comparing **with** and **without** the [[dat-sell-call-strategy|3x short-call option overlay]] that the IC authorized in principle on 2026-03-19 (Action #3).\n\n## Inputs\n\n| Input | Value | Source |\n|-------|------:|--------|\n| `Investment Company Ba'

---

## Finance — PN.35 principal

**Query:** `what is the principal of Promissory Note 35 from BG to BICL?`
**Canonical answer:** USD 39,023,179.25 principal (PN.35 — renews PN.34)

_Why this fails today:_ PN.35 = USD 39,023,179.25. PN.36 = USD 2.3M (different PN!). When the LLM mixes them up, the answer becomes wrong.

### Conflicting chunks in `finance_knowledge` (1 found)

- **score `0.604`** | source: `obsidian_vault`
  > 'om the parent on the same 3.5%, on-demand, unsecured terms as\nPN.35 (see [[2025-04-08-loan-pn35-39m]] and [[bicl-related-party-financing]]). The\nUSD 2.3M principal matches the **USD 2,300,000 dividend declared by BICL in FY2025** (see\n[[bicl-audited-financials-2025]]) — the timin'

### Conflicting chunks in `finance_docs` (1 found)

- **score `0.400`** | source: `brooker_database`
  > 'Renew PN.34).doc'

### Canonical chunks already in `finance_knowledge` (5 found — boost these)
- source: `obsidian_vault`
  > "- **On-demand risk:** as the note is payable on demand, the full amount is classified as a\n  current liability in BICL's balance sheet.\n\n## Source Evidence\n\n`No.35 LOAN AGREEMENT PN from BG = 39.02 USD Million (Renew PN.34).pdf` — single-page\nPromissory Note No.35, signed by Varu"
- source: `obsidian_vault`
  > '---\ntitle: "Promissory Note No.35 — USD 39.02M Loan, Brooker Group → BICL"\ntype: "decision_log"\ndepartment: "finance"\nstatus: "active"\ninstrument_id: "PN.35"\nsources: ["No.35 LOAN AGREEMENT PN from BG = 39.02 USD Million (Renew PN.34).pdf"]\nrelated: ["bicl", "bicl-corporate-profi'
- source: `obsidian_vault`
  > 'ker International Co., Ltd. (Authorized Director)"\ndecision_date: "2025-04-08"\ncreated: "2026-05-17"\nupdated: "2026-05-17"\ntags: ["finance", "decision", "loan", "promissory-note", "bicl", "related-party"]\n---\n\n# Promissory Note No.35 — USD 39.02M Loan, Brooker Group → BICL\n\n## De'

### Canonical chunks already in `finance_docs` (1 found — boost these)
- source: `brooker_database`
  > 'CENTAGE RATE 3.50 %\nLending Period: Start from April 8, 2025.\nThe entire principal and any accrued interest shall be fully and immediately payable\nUPON DEMAND of any holder thereof.\nAgreed To:\nBorrower: Mr. Varut Bulakul\nAuthorized Director\nBrooker International Co., Ltd.\nS\\BROOK'

---

## Summary

- Tests audited: **8**
- Conflicting chunks surfaced: **15**

### Recommended actions for data administrators
1. **Delete or relabel** stale chunks where the figure is genuinely outdated (e.g. `AUM Target: $500 mn` — replace with current $600M figure).
2. **Boost canonical chunks** by adding the question's keywords to the chunk header (e.g. add `40% rule numerator: Investment Company Baht (col H)` to the dashboard concept's header so it ranks first on that phrasing).
3. **For genuine paraphrase gaps** (no conflicts detected), add an alias header to the canonical chunk so embedding search reaches it.
4. **Re-run** `python scripts/api_test_pipeline.py --only use-case` after cleanup to confirm pass rate.