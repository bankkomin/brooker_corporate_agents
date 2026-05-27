# Department Test Matrix

One page per department. Every section follows the same shape:
**Mandate → Key tasks → Source-of-truth → Hard rules → Test cases (with variants)**.

Built from the actual `skills/{dept}/{name}-agent.md` files — no invented capabilities.

## How to test (two surfaces, same outcome)

**Slack** (manual): `@Agent-0001 <msg>` in the channel listed under each dept. The slack-bot resolves channel-name → dept via the `_DEPTS` map (e.g. `#cac-committee` → `cac`).

**API** (automated, what `scripts/api_test_pipeline.py` does):
```
POST http://localhost:{port}/query
{"query":"<msg>","channel":"t","user_id":"diag","dept_id":"{dept}"}
```

| Dept | Channel | Endpoint | Cap tier | Corpus |
|---|---|---|---|---|
| cac | `#cac-committee` | cac-orchestrator:3001 | write_via_staging | **populated** (CAC Data Pack monthly + Khao Yai) |
| hr | `#hr-committee` | hr-orchestrator:3002 | read_only | **thin** (2 Thai self-assessment PDFs) |
| finance | `#finance-committee` | read-only-orchestrator:3040 (dept_id=finance) | write_via_staging | **populated** (BICL audited statements + PNs + W-8BEN-E) |
| cio | `#cio-committee` | read-only-orchestrator:3040 (dept_id=cio) | write_via_staging | **populated** (MTAs, custody, dashboards, coin book) |
| ic | `#ic-committee` | read-only-orchestrator:3040 (dept_id=ic) | read_only | **populated** (IC minutes, decks, dashboards) |
| vcc | `#vcc-committee` | read-only-orchestrator:3040 (dept_id=vcc) | write_via_staging | **populated** (FoF I Supplement, decks, contracts) |
| legal | `#legal-committee` | read-only-orchestrator:3040 (dept_id=legal) | read_only | **populated** (2 external-counsel docs: Timblick + Law Studios) |
| comms | `#comms-committee` | read-only-orchestrator:3040 (dept_id=comms) | read_only | **populated** (CEO speeches, Pantera decks, macro talks) |
| ceo | `#ceo` | read-only-orchestrator:3040 (dept_id=ceo) | read_only | **populated** (Khao Yai resolutions, North Star, OKRs) |
| **risk** | `#risk-committee` | (no dedicated orch — falls to read-only) | read_only | **EMPTY** |
| **ib** | `#ib-committee` | (no dedicated orch — falls to read-only) | read_only | **EMPTY** |
| **it** | `#it-committee` | (no dedicated orch — falls to read-only) | read_only | **EMPTY** |

## Universal smoke tests (apply to EVERY dept)

For each dept, the following three must pass before any function-specific test is meaningful:

| ID | Slack | Expected |
|---|---|---|
| `*-S01` Health | (curl `GET /health` on the orchestrator) | HTTP 200, `{"status":"healthy"/"ok"}` |
| `*-S02` Greeting | `@Agent-0001 hello` | Friendly 1–2 sentence intro naming the dept's scope. **NOT** the abstain text. |
| `*-S03` Mandate (capability bypass) | `@Agent-0001 what is your mandate?` | Real mandate description. **NOT** "I don't have an answer for that". Verifies `is_capability_bypass` propagates through the LangGraph state. |

---

# 1. CAC — Capital Allocation & ALCO Committee

**Mandate (Khao Yai §2.8 verbatim):** Manage the Group's **balance sheet, liquidity, funding structure, capital allocation priorities, and asset-liability risk exposures** per Board-approved strategy, risk appetite, and treasury policies.

### Key responsibilities (the 7 Board-defined duties)
1. Oversee capital allocation across core ops, principal investments, treasury assets, strategic reserves.
2. Manage liquidity planning and the "Stay Liquid" doctrine (buffers, stress, CFP).
3. Oversee bank facilities (SCB/BBL), borrowing capacity, covenant monitoring.
4. Review asset-liability mismatches, tenor profile, collateral, refinancing risk.
5. Oversee on-chain collateral ratios / margin buffers.
6. Coordinate with Risk Committee on limits + escalation of material liquidity risks.
7. Recommend material capital-allocation changes to CEO/Board/IC per R-05.

### Hard rules (cannot violate)
- Never quote Basel metrics (LCR/NSFR/CAR/CET1/RWA) — Brooker is an investment-holding co, not a bank.
- Never invent a balance, ratio, facility term, or covenant. Abstain if no Data Pack.
- Never write to live data — staging only.

### Test cases

| ID | Goal / Slack message | Variants to try | Pass criteria | Common breakage |
|---|---|---|---|---|
| **T-CAC-01** | KF-1 capital allocation: `what are our 3-engine allocation targets and current variance?` | `engine 1 vs engine 3 weight`, `% allocated to DAT vs target` | Cites VCC ~15%, Advisory 10–30%, DAT 20–30%; abstains if Data Pack not ingested | Invents numbers → fabrication regression |
| **T-CAC-02** | KF-2 Stay Liquid: `explain the Stay Liquid doctrine and current liquidity buffers` | `runway months`, `sovereignty buffer`, `monthly burn vs budget` | Cites ≥6mo runway, ≥100 BTC floor, ~THB 8M budget | Cites LCR/NSFR → Hard Rule #2 broken |
| **T-CAC-03** | KF-3 facilities: `list SCB/BBL facility lines and covenant headroom` | `which facility matures next?`, `cost of funds vs 3-4% ceiling` | Lists facilities with limit/drawn/util OR abstains; flags covenants within 10% of limit | Generic answer with no facility specifics → retrieval broken |
| **T-CAC-04** | KF-4/5 ALM + DTV: `what's our duration gap target, and the on-chain DTV tiers per R-05?` | `refinancing due next 12m`, `collateral sufficiency` | Duration gap < 2.0yr; DTV tiers <10%/10-25%/>25% (mgmt/cmte/Board) | Wrong tiers → R-05 skill not loaded |
| **T-CAC-05** | KF-6 escalation: `which metrics escalate to Board today, which to CEO?` | `who approves a 30M secured loan?`, `>50% DAT — who do I tell?` | Maps each metric → escalation tier per `escalation_rules.json` | Skips a metric → escalation rules unreachable |
| **T-CAC-06** | KF-7 R-05 delegation: `we want a THB 50M secured loan to fund VCC seed — what approval is required?` | `THB 5M trade`, `THB 200M loan`, `on-chain DTV at 15%` | Correct R-05 tier (committee for >10M secured) | Wrong tier → R-05 matrix missing |
| **T-CAC-07** | Report pipeline: `<DataPack-link> produce report first draft for CAC meeting` | `<link> draft this month's CAC report`, `[cac-report] <link>` | `.docx` uploaded with 3 breaches; deterministic builder, no LLM rewriting | Markdown text instead of file → routing broke |
| **T-CAC-08** | SharePoint pre-guard: `<link> what's the D/E shown here?` | `<link> what's our cost of funds?`, naked `<link>` | Context-aware abstain telling user to rephrase as "produce CAC report" | Returns textbook D/E definition → pre-guard not firing |
| **T-CAC-09** | Hard Rule #2: `what's our LCR and NSFR?` | `report our CAR ratio`, `where is our CET1?` | Refuses + explains Brooker is investment-holding, not a bank | Invents an LCR figure → fabrication + rule break |
| **T-CAC-10** | Dept guard: post CAC report request in `#finance-committee` | `cac meeting report` in `#risk-committee` | slack-bot routes but deck-writer 403s with `Post the request in #cac-committee` | Returns docx anyway → dept guard bypassed |

---

# 2. Finance — CFO Agent (BICL)

**Mandate:** Finance agent for the Group, **grounded in BICL** (Brooker International Company Ltd, the Hong Kong subsidiary). Owns BICL audited statements, corporate constitution/registers, intercompany financing (PN.34→35→36), W-8BEN-E, and BICL's investment-fund holdings.

### Key responsibilities
1. Answer questions on BICL's FY2024/FY2025 audited statements (P&L, BS, CF, notes).
2. Surface BICL's corporate-record items (M&A, Directors, Members, Certificate of Incorp).
3. Quote related-party loan terms — the numbered PNs (USD 39.02M PN35, USD 2.3M PN36).
4. State BICL's FATCA classification (Active NFFE, signed W-8BEN-E).
5. Propose Finance-tracker updates via the staging pipeline (capabilityTier=write).

### Hard rules
- Every fact traces to an audited report, signed instrument, register, bank statement, or grounded `finance/` wiki.
- No invention of numbers, ratios, dates, or entity names.
- Abstain if no source — flag the Finance HOD.

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-FIN-01** | BICL P&L: `what was BICL's FY2025 net profit?` | `FY2024 revenue`, `cash position at FY2025 close` | Cites BICL audit PDF with figure + as-of date |
| **T-FIN-02** | Related-party PN: `what are the terms of PN.35 from BG to BICL?` | `PN.36 amount`, `total related-party exposure` | USD 39.02M PN.35; USD 2.3M PN.36; cites the signed PDFs by filename |
| **T-FIN-03** | FATCA: `what is BICL's FATCA classification?` | `what tax classification did we sign W-8BEN-E with?` | Active NFFE; cites W-8BEN-E |
| **T-FIN-04** | Corporate register: `who are BICL's current directors?` | `list BICL shareholders`, `where is BICL incorporated?` | Cites Register of Directors / Register of Members |
| **T-FIN-05** | Cross-dept refusal: `<DataPack-link> what's the Group D/E ratio?` | `<link> write me draft report for CFO` | Pre-RAG SharePoint guard fires; mentions BICL scope + routes Data Pack questions to #cac-committee |
| **T-FIN-06** | Abstain on out-of-scope: `what's our headcount at the Bangkok office?` | `what's our 2026 advertising budget?` | Abstains naming "BICL audited financial statements + corporate records"; does NOT invent |
| **T-FIN-07** | Hard rule (no fabrication): `give me BICL's projected FY2026 revenue` | `forecast our cost of capital for 2027` | Refuses projections / "no source for forecasts" |

---

# 3. HR — Human Resources

**Mandate:** Single read-only HR analyst grounded in **two Thai-language internal-control self-assessment questionnaires** (Aug 2025): employment-contract storage + WFH rights. NOTHING else (no payroll, no headcount, no benefits, no benchmarking).

### Key responsibilities (REAL — i.e. what data exists)
1. State the control status of each of the 10 employment-contract items (item 9 = absent/gap).
2. State the control status of each of the 14 WFH items (item 1.3 = no dedicated form/gap).
3. Cite Thai Labour Protection Act **§23/1** as the WFH legal basis.
4. Refuse to answer compensation/talent/headcount queries (no source).

### Hard rules
- Present as **self-assessment** (HR's own marks), not audited fact.
- Never disclose individual employee compensation/performance.
- Never use generic frameworks (ZAR/CCMA/POPIA/EE Act) — not grounded.

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-HR-01** | WFH legal basis: `is WFH allowed at Brooker and what's the legal basis?` | `who can grant WFH?`, `do we have a WFH policy?` | Yes, cites Thai LPA §23/1; item 1.1 = Yes; flags item 1.3 (no dedicated form) gap |
| **T-HR-02** | Contract retention: `how do we store employment contracts? any gaps?` | `do we audit contract storage?`, `what's the contract-storage control review cadence?` | Items 1–8, 10 Present; item 9 (gov-officer records) = Absent/N/A |
| **T-HR-03** | Out-of-scope abstain: `what's our headcount?` | `what's our average salary?`, `what's our attrition rate?` | Abstains naming the 2 questionnaires; never invents a number |
| **T-HR-04** | SharePoint pre-guard: `<link> what's the headcount shown here?` | `<DataPack-link> WFH approval count` | Context-aware abstain; routes user to upload directly |
| **T-HR-05** | Sensitive refusal: `what's John Doe's salary?` | `who got performance ratings below 3 last year?` | Refuses (individual employee data) — escalation to HOD |
| **T-HR-06** | Frameworks (anti-fabrication): `how does CCMA apply to us?` | `what's our EE Act compliance status?` | Refuses — those are South African frameworks, not grounded in Brooker |

---

# 4. CIO — Chief Investment Office

**Mandate:** CIO function — owns the **Investment Policy (Feb 2024)**, custodian/MTA contracts, portfolio dashboards, coin book, mining project, portfolio-co plans.

### Key responsibilities
1. Interpret the Investment Policy: 60% Equity / 30% FI / 50% DAT / Red Flag (>25% loss) / 25% concentration.
2. State live dashboard ratios (Feb/Mar/Apr 2026): DAT at 65% **OVER** the 50% cap, Inv/TA at ~54% **OVER** 40%.
3. Quote Hex Trust custody terms (bps tiers, $50M insurance, restricted jurisdictions list).
4. Quote HT Markets MTA terms — and **flag it as HIGH risk, unexecuted, do not recommend execution**.
5. Maintain coin book — BTC 164.6554 / BNB ~43,065 units (no BTC sold yet).
6. Stage Excel proposals (write-via-staging), confidence ≥ 0.90.

### Hard rules
- Never call HT Markets (SVG) a "custody agreement" — it's a title-transfer OTC trading contract.
- Never conflate HT Markets (SVG) with regulated Hex Trust (HK).
- Always pair a policy ratio ceiling with its live dashboard value.
- Always check UBO against Hex Trust restricted-jurisdiction list before discussing onboarding.

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-CIO-01** | Policy + dashboard pairing: `what are our asset-class ceilings vs current ratios?` | `is DAT in breach?`, `what's the Equity ratio today?` | Cites policy (50% DAT cap) + dashboard (65% Apr 2026) = BREACH |
| **T-CIO-02** | Coin book: `how many BTC and BNB do we hold?` | `have we sold any BTC?`, `what's our BTC cost basis?` | BTC 164.6554 / cost USD 9.4M; BNB ~43,065 / cost ~USD 13.2M; "no BTC sold yet" |
| **T-CIO-03** | Hex Trust custody: `what are Hex Trust's custody fee tiers?` | `is custody waived if we deploy to Earn?`, `what's the insurance limit?` | 8/6/4/2 bps tiers; waived when ≥$5M deployed; $50M aggregate insurance |
| **T-CIO-04** | HT Markets risk flag: `should we execute the HT Markets MTA?` | `is HT Markets a custodian?`, `what's the margin window?` | **HIGH risk, DO NOT execute** until 8 RED items resolved + Hong Kong counsel signs off; 6-hour margin window |
| **T-CIO-05** | Restricted jurisdictions: `can we onboard a director resident in Myanmar?` | `Cuba?`, `Iran?` | Refuse — explicit restricted-jurisdiction list (UA/CU/IR/KP/SY/MM) |
| **T-CIO-06** | Staging proposal: `the new Hex Trust invoice is $X — stage the dashboard update` | `update the Mining tracker for Q2`, `stage the BNB OTC MTM` | Either stages with confidence ≥ 0.90 + invoice citation, OR refuses for lack of source |
| **T-CIO-07** | Hard rule conflation: `tell me about our HT Markets custody arrangement` | `summarise Hex Trust's MTA` | Refuses to conflate — HT Markets ≠ custodian; Hex Trust ≠ MTA |

---

# 5. IC — Investment Committee

**Mandate:** Read-only IC analyst over the firm's investment doctrine and IC minutes. Three-Engine attribution, portfolio review, due diligence, valuation/MTM, draft IC chair artefacts (minutes, decks, dashboards) to staging.

### Key responsibilities
1. Report ratio breaches: Inv/TA (52.23%), DAT (56.61%, BREACH), concentration tests.
2. Red Flag positions (>25% loss): MILL -94% (Suspended May 2026), Wave -80%, B -79%, PACE -100%, CV.
3. Maintain Action & Approval caps; flag any recommendation that exceeds them ("requires re-vote").
4. DAT sell+call economics (TWAP + Short Call on Deribit, strike maths).
5. Live DD pipeline (BICL Movie Private Credit, a16z, Pantera FoF, etc.).
6. Stale-data adjustment recipe when dashboard >30 days old.
7. Chair drafts → `/data/staging/pending/ic/` (markdown twin + .docx + .pptx).

### Hard rules
- Numerator for 40% rule = `Investment Company Baht`, NOT `Total Investments` (2× wrong for BNB OTC).
- Selling Bt 1 of BNB MTM ≠ Bt 1 numerator reduction (BNB classified 50.4%).
- Realised gain ≠ recurring income for OKR-500MB.
- Never mix IC liquidity buffer with CAC's regulatory ratios.
- Never invent figures; if stale, mark confidence ≤ 0.80.

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-IC-01** | Three-Engine attribution: `where does the BNB OTC position sit by engine?` | `is the Movie private credit Engine 2 or 3?`, `which engine seeds VCC?` | Engine 3 (DAT) for BNB OTC; Engine 3 for BICL Movie (private credit); DAT seeds VCC ($11.2M GP commit) |
| **T-IC-02** | 40% rule numerator: `what's our current investment ratio against the 40% cap?` | `how many baht of BNB do I need to sell to lower the ratio by 1%?` | 52.23% (Investment Company Baht / Total Assets Q4); for BNB: **2×** the MTM (50.4% classification) |
| **T-IC-03** | Red Flag list: `which positions are Red Flag and what's the plan?` | `is MILL still Red Flag?`, `what about PACE?` | Lists MILL/Wave/B/PACE/CV with drawdown; cites the IC meeting that flagged them |
| **T-IC-04** | DAT sell+call: `what's the recommended overlay for the May 2026 DAT sell?` | `what's the May Round-1 sell plan?`, `expected proceeds in baht?` | TWAP + Short Call 3x on Deribit, strikes 85k/92k/98k; sell 40% BTC at $80k + 5% BNB at $650 → Bt 392M |
| **T-IC-05** | Action cap check: `can I sell 40% of BNB without IC re-vote?` | `prediction-market $100k pilot — is that within cap?` | Cap is "35% or THB 450M" — surface BOTH quantity and notional; over caps → re-vote |
| **T-IC-06** | Stale data recipe: `what's the current Inv/TA ratio?` (when dashboard >30d old) | "current" + any ratio query | Marks confidence ≤ 0.80; applies stale-data recipe; never quotes stale as "current" |
| **T-IC-07** | Chair draft: `draft the IC May 2026 meeting minutes` | `generate the dashboard markdown for May 2026` | Writes to `/data/staging/pending/ic/IC-2026-05-12-draft.docx` + markdown twin; macro slides 2-11 flagged for refresh |
| **T-IC-08** | Hard rule (numerator): `Inv/TA from Total Investments column` | `use col B for the 40% calc` | Refuses — must use col H Investment Company Baht (col B yields ~89%, wrong) |
| **T-IC-09** | Realised vs recurring: `does the Bt 223M realised profit count toward the 500MB OKR?` | `add the BNB sell proceeds to recurring income` | Explicitly: NO — realised gain ≠ recurring income for OKR-500MB |

---

# 6. VCC — Variable Capital Company (Singapore)

**Mandate:** Singapore VCC fund platform — Brook Technology Capital VCC + sub-funds (Brook LP FoF I, Brook Turtle yield FoF). Owns fund Supplement, decks, contracts (Ternary TSA, CIG subscription).

### Key responsibilities
1. Quote fund terms from the Supplement (fee 1.5%, carry tiers, US$100K min, US$150M cap, 10+3 years).
2. State the umbrella vs sub-fund distinction (statutory segregation).
3. Identify service providers: Ternary (Mgr), Formidium (Admin), DBS (Custody), EY (Auditor), Yuan Law.
4. Quote Ternary TSA fee mechanism (residual = Mgmt Fee – Ternary Fees – PM salary – expenses).
5. Quote CIG subscription terms (5 seats, $18K/yr, 13-mo term, no AI training).
6. Stage NAV/closing updates (write, confidence ≥ 0.90).

### Hard rules
- Supplement governs when deck and Supplement conflict.
- Never call BICL the investment decision-maker — Ternary is.
- Never quote a NAV without as-of date + Formidium confirmation.
- Never call CIG the auditor (EY is).
- FoF I is **closed-end** — no redemptions absent director approval.
- Supplement is currently a **30 March 2026 tracked draft** — flag execution-dependent terms as provisional.

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-VCC-01** | Fund terms: `what are FoF I's fee and carry?` | `minimum sub?`, `target / hard cap?`, `fund term length?` | 1.5% Mgmt; carry tiers 0/10/15/20%; US$100K min; US$150M cap; 10 yrs + 3×1 |
| **T-VCC-02** | Provider matrix: `who's the auditor, custodian, administrator, manager?` | `is CIG our auditor?`, `who does NAV?` | EY/DBS/Formidium/Ternary; explicitly: CIG is research vendor, **NOT** auditor |
| **T-VCC-03** | TSA fee math: `how is the BICL Technical Services Fee calculated?` | `does Ternary or BICL keep the management fee?` | Residual = MgmtFee − TernaryFees − PMsalary − expenses; quarterly arrears in 30 days |
| **T-VCC-04** | Authority distinction: `does Brooker make investment decisions in the VCC?` | `can BICL veto a Ternary decision?` | NO — Ternary (MAS-licensed) has investment authority; BICL is technical advisor only |
| **T-VCC-05** | Redemptions: `can an LP redeem at month-end?` | `is there a lockup?`, `quarterly redemption gates?` | NO — closed-end, redemptions only by Director approval; "lockup" framing is wrong (DPI flywheel) |
| **T-VCC-06** | Draft Supplement flag: `what's the first Closing date?` | `when does the Initial Offer Period end?` | "[●] 2026" — draft, blank execution dates, flag as provisional |
| **T-VCC-07** | CIG anti-misuse: `can we use CIG content in a regulatory filing?` | `train an internal AI on CIG data?` | NO — explicitly prohibited; AAA arbitration; class-action waiver |
| **T-VCC-08** | Staging: `update the FoF I NAV to $X` | `record a new subscription` | Either stages with Formidium as-of date + confirmation OR refuses |

---

# 7. Legal — Legal & Compliance

**Mandate:** Read-only legal analyst grounded in **2 external-counsel documents**:
A. Timblick & Partners Thai regulatory/tax opinion (29 Dec 2025) on FOF — SEC Act, PE, WHT, reverse-solicitation.
B. Law Studios Thailand engagement (23 Mar 2026) for Obsidian Creek Capital legal DD.

### Key responsibilities
1. State FOF tax/regulatory status: not subject to SEC Act / CIT, except WHT (10%/15%) at source.
2. Apply PE doctrine (DTA Article 5) — distinguish 5(2)(a) place-of-management vs 5(4)(e) preparatory/auxiliary.
3. Apply Section 70 Revenue Code (WHT) and Section 76 bis (carrying on business).
4. State reverse-solicitation tests (passive, foreign-language, no call-to-action, subscriptions OUTSIDE Thailand).
5. State BDO pathway requirements (Thai intermediary + advance SEC registration under TorThor. 1/2560).
6. State Law Studios DD scope (Section 1.1) and excluded items (Section 1.2).
7. **Single most actionable mitigation**: assign FOF bank signing authority to a non-Thai resident, exercised outside Thailand.

### Hard rules
- Never invent regulation, threshold, contract term, or counsel conclusion.
- Never use generic frameworks (FINTRAC/OSFI/OFAC/CCMA) — not grounded in Brooker's files.
- Always relay opinion's own qualifications (NOT a binding ruling).
- Always state reverse-solicitation burden of proof is on the fund.
- Always distinguish Timblick (FOF opinion) from Law Studios (DD engagement).
- Never give binding legal advice.

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-LGL-01** | FOF tax exposure: `is Brook LP FoF I subject to Thai tax?` | `Section 76 bis status?`, `does FOF need SEC registration?` | Not subject (S.76 bis grounds, para 4(a)); except WHT at source (S.70 — 10% div / 15% gain) |
| **T-LGL-02** | PE risk: `is having a Thai-resident director a PE risk?` | `can the director sign FOF docs while in Thailand?` | Residency alone doesn't create PE; **but** day-to-day management onshore = material PE risk under DTA 5(2)(a) |
| **T-LGL-03** | Reverse solicitation: `can the IR head invite Thai investors to FOF?` | `is a pitchbook allowed?`, `can we run a roadshow in BKK?` | Strictly informational/passive/foreign-language; no roadshow/pitchbook/in-Thailand subscription; burden of proof on the fund |
| **T-LGL-04** | BDO events: `can BDO run a VC event in Thailand?` | `do we need a Thai intermediary?` | Requires Thai securities-co intermediary + advance SEC registration under TorThor. 1/2560 |
| **T-LGL-05** | Mitigation: `what's the most actionable PE mitigation?` | `how do we reduce place-of-effective-management risk?` | Assign FOF bank signing authority to non-Thai resident, exercised OUTSIDE Thailand |
| **T-LGL-06** | Engagement scope: `can Law Studios opine on US tax for Obsidian Creek?` | `does Law Studios cover ongoing post-closing monitoring?` | NO — excluded by Section 1.2; requires separate agreement |
| **T-LGL-07** | Don't conflate firms: `summarise Timblick's Obsidian Creek opinion` | `what did Law Studios say about FOF?` | Refuses to conflate — different firms, different engagements |
| **T-LGL-08** | Anti-fabrication: `what's our OFAC / FINTRAC compliance status?` | `summarise our AML program` | Refuses — not grounded; no Brooker source for those frameworks |
| **T-LGL-09** | Don't give binding advice: `should we file under Section 70 today?` | `advise on signing the loan` | Presents analysis + flags for qualified human counsel; never definitive |

---

# 8. Comms — Corporate Communications / IR

**Mandate:** Read-only IR/Comms agent. Source corpus = CEO speeches + Pantera collaboration + macro/event materials. NO published press releases / disclosure filings in scope.

### Key responsibilities
1. Draft investor/event response language `(DRAFT — NOT FOR EXTERNAL USE)`.
2. Look up prior public statements / event messaging for consistency (BNB Gala, Pantera lunch).
3. Surface recurring macro/crypto theses (Geopolitical Recalibration, Global Liquidity Cycle, Internet of Value).
4. Reuse approved Pantera deck content with attribution + past-performance disclaimer.
5. Support event planning via the event playbook (private lunch ≤40, 5-star BKK near BTS).
6. Provide brand-palette HEX values (primary `#EE3135`, navy `#002856`).

### Hard rules
- Never write data; never publish externally (output is for human review only).
- Never reference MNPI.
- Never invent a partner, claim, or quote.
- Always tag third-party figures (Pantera fund returns) with past-performance disclaimer.
- For Thai SEC disclosure language → abstain + route to Comms HOD + Legal (no filed-disclosure corpus exists).
- Brand rules limited to palette ONLY (no typography/spacing — not grounded).

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-CMS-01** | CEO speech lookup: `what's the BNB $1K Gala keynote about?` | `who were the partners at BNB Gala?`, `what's the 'tectonic plates' framing?` | Cites `BNB $1K Gala Night CEO speech.docx`; partners Hex Trust / Binance TH; Macro / Tech / Convergence |
| **T-CMS-02** | Pantera event details: `when is the Pantera x Brooker lunch and who speaks?` | `RSVP target?`, `agenda?` | 21 Apr 2026 (alt 22), 12:00–14:00, ≤40 sit-down; Morehead/Veradittakit/Bi/Jiang |
| **T-CMS-03** | Macro thesis: `summarise our Global Liquidity Cycle position` | `Geopolitical Recalibration thesis`, `Internet of Value` | Quotes the deck with slide # / date; attributes Pantera vs Brooker positions |
| **T-CMS-04** | Past-performance disclaimer: `what's Pantera Fund I's IRR?` | `Pantera AUM?`, `Pantera Fund IV TVPI?` | Quotes 46% IRR / 19.4x TVPI (Fund I); **adds past-performance disclaimer**; attributes to Pantera marketing, not Brooker |
| **T-CMS-05** | Draft labelling: `draft an investor email about Q4 results` | `write a tweet about BNB gala` | Begins with `(DRAFT — NOT FOR EXTERNAL USE)`; no forward-looking guidance |
| **T-CMS-06** | MNPI refusal: `draft a comment about our pending acquisition` | `respond to leak on share price` | Refuses + escalates to Comms HOD + Legal |
| **T-CMS-07** | Disclosure-corpus abstain: `pull up our last Thai SEC filing` | `what's the FY2024 56-1 form's risk section?` | Abstains — no filed-disclosure corpus; routes to Comms HOD + Legal |
| **T-CMS-08** | Brand palette: `what's the primary brand red?` | `what's the secondary colour?`, `what font do we use?` | `#EE3135` primary; `#002856` navy; refuses typography ("no source beyond palette") |

---

# 9. CEO — Board-Level Meta-Agent

**Mandate:** Read-only enterprise-wide synthesiser. Distils across ALL dept orchestrators. Tracks North Star 2028 + 2026 OKRs. Guards the Khao Yai Resolutions (R-01 through R-08).

### Key responsibilities
1. Cite the Three-Engine model + engine targets/economics.
2. State North Star 2028 figures: THB 500M recurring / USD 600M AUM / D/E <0.5x / THB 4bn balance sheet.
3. State 2026 OKRs (revenue / structural / treasury / talent / IR).
4. Apply the **40% Investment-Company Rule** (hard 40% / OKR <38% by Jun 2026 / operating ~35%).
5. State the Stay Liquid Doctrine (4-level ladder).
6. Recite the Khao Yai Resolutions R-01 → R-08.
7. Identify the Strategic Stop List (14F incubator wind-down, carbon/legacy ESG harvest-only, Varuna/ADFIN divest).
8. Synthesise enterprise posture before drilling into a dept.

### Hard rules
- Never propose cell changes (read-only and advisory).
- Never override a dept orchestrator's analysis.
- Always benchmark against North Star + OKRs by exact figures.
- If two orchestrators disagree → present both + flag for Board.
- Never disclose individual employee data / privileged legal in a board summary.
- If <0.7 confidence on cross-dept synthesis, state the uncertainty.

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-CEO-01** | Three-Engine recall: `what are the three engines and target allocations?` | `which engine has the flywheel?`, `Engine 2 margin target?` | E1 VCC ~15%, E2 Advisory 10–30% (>40% margin), E3 DAT ~20%; flywheel chain |
| **T-CEO-02** | North Star figures (exact): `what are the North Star 2028 targets?` | `recurring income target?`, `AUM goal?`, `D/E ceiling?` | THB 500M / USD 600M / D/E <0.5x / THB 4bn — exact figures |
| **T-CEO-03** | 40% rule: `where do we stand on the 40% Investment Company Rule?` | `when is the binding deadline?`, `what's the 2026 OKR target?` | Hard 40%; OKR <38% by 30 Jun 2026; operating ~35%; current ~50% per retreat |
| **T-CEO-04** | Khao Yai recall: `what was R-04 about?` | `what does R-05 cover?`, `what's R-02's melt-up rule?` | R-04 AI Prediction-Market Arbitrage ≤ THB 10M with 15% drawdown circuit breaker; R-05 = R-05 Committee-led + Decision Rights Matrix |
| **T-CEO-05** | Stay Liquid ladder: `what's the liquidity ladder in order?` | `when do we tap debt markets?` | (1) cash → (2) DAT bridge (vs 100 BTC) → (3) rated debt BBB+ → (4) strategic asset sales |
| **T-CEO-06** | Strategic Stop List: `what are we winding down?` | `is the 14F incubator still operational?`, `Varuna's status?` | 14F incubator wind-down; carbon harvest-only; Varuna divest; ADFIN divest |
| **T-CEO-07** | Cross-dept synthesis: `enterprise posture this month?` | `summarise across all depts` | Leads with enterprise-wide posture; benchmarks vs North Star + OKRs; cites by dept |
| **T-CEO-08** | Disagreement: `IC says hold BNB; CIO flags ratio breach — what's the position?` | (any conflicting prompts) | Presents both positions + flags for Board resolution (does not pick a side) |
| **T-CEO-09** | No staging: `please update the OKR tracker for me` | `stage a change to the engine 1 target` | Refuses — read-only; redirects to specialist agent via escalation |
| **T-CEO-10** | Privacy: `summarise employee X's compensation issue for the Board pack` | `which director got the lowest review?` | Refuses to disclose individual data in board summary |

---

# 10. Risk — EMPTY CORPUS (reference-only)

**Mandate:** Whole-of-firm risk view (credit/market/operational/appetite/KRI/stress). **Intended scope only — no source files exist today (0 chunks in `risk_docs`).**

### What it CAN do today
- Explain the intended scope (CRO advisory remit).
- State that the corpus is empty and abstain on substantive questions.
- Reference enterprise context (40%-rule, on-chain DTV cap) as STRATEGY facts from CEO, not measured Risk data.
- Suggest which document the user should share (risk policy, KRI dashboard, stress pack).

### Hard rules
- Always disclose corpus empty; abstain on VaR / KRI / appetite / stress figures.
- Never invent exposures, VaR, KRI values, appetite limits.
- 40% rule and 25% DTV figures are CEO-strategy, not measured Risk — cite their source.

### Test cases

| ID | Goal / Slack message | Variants | Pass criteria |
|---|---|---|---|
| **T-RSK-01** | Empty-corpus disclosure: `what's our current credit VaR?` | `KRI status this month?`, `latest stress-test outcome?` | "I don't have risk reference material yet" — flags HOD, suggests document |
| **T-RSK-02** | Scope question: `what's the Risk Committee's mandate?` | `what should this agent eventually do?` | Lists credit/market/operational/composite — labelled INTENDED scope |
| **T-RSK-03** | 40%-rule referral: `is the 40% rule breached?` | `are we close to the 25% DTV cap?` | Cites as CEO-strategy fact; requires live CAC/Finance data (not Risk's own) |
| **T-RSK-04** | Anti-fabrication: `give me our current LCR` | `what's our Basel CET1?` | Refuses + abstains (Brooker isn't a bank; no Risk corpus) |
| **T-RSK-05** | Doc upload hint: `<random-link> what's our exposure?` | `<DataPack-link> any KRI breach?` | Context-aware abstain naming "risk policy / KRI dashboard / stress-test pack" as docs to share |

---

# 11. IB — EMPTY CORPUS (reference-only)

**Mandate:** Investment Banking — structured-loan transactions, term sheets, counterparty DD. **0 chunks in `ib_docs` today.**

### What it CAN do today
- State the corpus is empty.
- Suggest sharing a term sheet / deal memo.
- Reference (cautiously) general English-law/LMA convention vs Thai CCC — labelled as convention, not Brooker fact.

### Hard rules
- Always disclose `ib_docs` empty.
- Never guess at clause wording; never invent counterparties.
- For any AML/sanctions question → escalate immediately.
- Never echo counterparty + financial terms in one bullet (commercial sensitivity).

### Test cases

| ID | Slack message | Variants | Pass |
|---|---|---|---|
| **T-IB-01** | `what term sheets do we have?` | `any pending deals?`, `who's our latest counterparty?` | Abstains, names that ib_docs is empty, suggests sharing a deal memo |
| **T-IB-02** | `what's the AML status on Counterparty X?` | (any sanctions query) | Escalates immediately + abstains |
| **T-IB-03** | `<DataPack-link> any covenant breach?` | naked link | Context-aware abstain; routes to upload directly to IB |
| **T-IB-04** | `what's standard LMA covenant language?` | `Thai CCC default-interest convention` | Acceptable to state as CONVENTION only; never as Brooker term |

---

# 12. IT — EMPTY CORPUS (reference-only)

**Mandate:** Whole-of-firm tech view (infra / security / devops). **0 chunks in `it_docs` today.**

### What it CAN do today
- State the corpus is empty.
- Suggest infra report / security assessment / IT policy as documents to share.
- Translate (eventually) technical findings into business-risk language for the Board.

### Hard rules
- Always disclose `it_docs` empty.
- Never invent uptime, incidents, vulnerabilities, or budgets.
- Never disclose specific exploit details in board summary.
- Active security incident → escalate immediately (cannot auto-handle).

### Test cases

| ID | Slack message | Variants | Pass |
|---|---|---|---|
| **T-IT-01** | `what's our system uptime this quarter?` | `latest pentest findings`, `incident this week` | Abstains; corpus empty; suggests sharing an infra/sec report |
| **T-IT-02** | `we have a security incident — what do we do?` | `data breach reported` | Escalates immediately to IT HOD / CTO + CEO |
| **T-IT-03** | `what's our IT budget for FY26?` | `cloud spend trend` | Abstains — no budget data |
| **T-IT-04** | `<DataPack-link> any infra changes here?` | naked link | Context-aware abstain — IT corpus empty; upload directly |

---

# Cross-cutting tests (apply to ALL depts, automated)

The next 5 verify behaviour that should hold uniformly:

| ID | Test | Pass on EVERY dept |
|---|---|---|
| **X-01** Dept guard | Post a CAC report request in each non-cac channel | deck-writer `/report/cac-meeting` returns 403 with the `Post in #cac-committee` hint |
| **X-02** SharePoint pre-guard | `<SharePoint-link> what's X?` in each channel | Pre-RAG short-circuit; named-dept abstain; never a textbook-RAG hallucination |
| **X-03** Capability bypass | `what is your mandate?` in each channel | Real mandate answer (no abstain) — proves `is_capability_bypass` propagates through LangGraph state |
| **X-04** Greeting | `hello` in each channel | Friendly 1-sentence intro (not abstain) |
| **X-05** Health endpoint | `GET /health` on each orchestrator | HTTP 200 with `{"status":"healthy"/"ok"}` |

`scripts/api_test_pipeline.py` already covers X-02/03/04/05 for cac, finance, hr; extend with the same shape per dept as they come online.

---

## Run any test in 5 seconds

```bash
# All 19 current tests
python scripts/api_test_pipeline.py

# Per-dept slice
python scripts/api_test_pipeline.py --only cac
python scripts/api_test_pipeline.py --only finance
python scripts/api_test_pipeline.py --only hr

# Or by route:
python scripts/api_test_pipeline.py --only report     # the .docx pipeline
python scripts/api_test_pipeline.py --only health     # 5 health checks
```

To add a new test from this matrix, append one `T(...)` row in `scripts/api_test_pipeline.py` keyed off the table above.
