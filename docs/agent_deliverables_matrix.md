# Agent deliverables per department

Maps each dept-agent's expected `.docx` reports, `.xlsx` trackers/proposals, and `.pptx` decks. Built from each `skills/{dept}/{name}-agent.md` mandate + what's already in `config/templates/`.

**Legend:**
- ✅ **DONE / template exists** — verifiable end-to-end today
- 🟡 **named in SKILL.md** — agent is supposed to produce this; pipeline not built yet
- 📝 **implied by responsibilities** — not explicit but a clear gap
- ❌ **deferred** — corpus empty or out of scope until data arrives

---

## 1. CAC — Capital Allocation & ALCO Committee
`capabilityTier: write_via_staging`

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **CAC Monthly Report — First Draft** (To: CFO Supane, from CAC; balance sheet, liquidity, funding, ALM, on-chain, risk-appetite, policy compliance, recommendations) | ✅ **DONE** | Built this session: `gen_cac_report_from_xlsx.py` + deck-writer `/report/cac-meeting`. Verified 6/6 facts in actual file |
| Report `.docx` | Bank-facility review memo (SCB/BBL — limits, util, covenant headroom, renewal status) | 🟡 | sub-component of CAC report; could be extracted as a standalone memo |
| Report `.docx` | Quarterly stress-test memo (-25% DAT / -50% cash / combined scenarios) | 🟡 | sub-component today; standalone for board pack |
| Excel `.xlsx` | **ALCO Tracker update** via staging — cell-precise proposals (e.g. `E8 = 3.15%` for facility rate) | 🟡 | `staging_writer.py` exists; `config/excel_schema/alco_tracker.json` is the cell-map config that must be populated. **Highest-priority untested write path.** |
| Excel `.xlsx` | Covenant-watch sheet (any covenant within 10% of limit) | 🟡 | could land in the ALCO Tracker as a tab |
| PowerPoint `.pptx` | Monthly CAC committee deck (headline ratios + breach table + recommendations) | 🟡 | uses `config/templates/brooker/brooker-deck-template.pptx`; deck-writer `/compose` can render it from a brief |

---

## 2. CIO — Chief Investment Office
`capabilityTier: write_via_staging` (confidence ≥ 0.90)

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | Hex Trust custodian fee-invoice reconciliation memo | 🟡 | bps tiers + waiver rules from `[hex-trust-custody-fee-supplement]` |
| Report `.docx` | HT Markets MTA risk update (the OPEN HIGH-risk review memo periodic refresh) | 🟡 | `HT_Markets_MTA_Review_Memo.docx` template precedent |
| Report `.docx` | Portfolio-company review (Asian Finance / BSFL monthly) | 🟡 | per `[asian-finance-business-plan]` + `[bsfl-monthly]` series |
| Excel `.xlsx` | **Portfolio Dashboard monthly sheet** (Feb→Mar→Apr→May...) — ratio + investment-company classification rolls | 🟡 | `Dashboard Feb2026.xlsx` is the source-of-truth pattern; staging proposal would add the next month tab |
| Excel `.xlsx` | Coin Weekly Report (.pdf historically, but could be .xlsx) — BTC/BNB units, cost, MTM | 🟡 | `[digital-asset-coin-book]` pattern |
| Excel `.xlsx` | KYC checklist update (Hex Trust corporate onboarding) | 🟡 | static checklist; not a heavy staging path |
| PowerPoint `.pptx` | CIO board briefing on policy ratios + custody + counterparty status | 🟡 | brooker template |

---

## 3. IC — Investment Committee (chair function)
`capabilityTier: read_only` (chair drafts → staging)

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **IC monthly meeting minutes** (engine-attributed sections, Action & Approval cap table, DD pipeline, Red Flag list) | ✅ **template exists** | `config/templates/ic/IC-meeting-minutes-reference.docx` — pipeline land in `/data/staging/pending/ic/IC-{YYYY-MM-DD}-draft.docx` |
| Report `.md` | Markdown twin of minutes (RAG-indexable) | 🟡 | per skill — lands in `obsidian-vault/ic/meeting-notes/IC-{YYYY-MM-DD}-draft.md` |
| Excel `.xlsx` | **IC Dashboard** — portfolio ratios + Red Flag drawdowns + concentration | ✅ **template exists** | `config/templates/ic/IC-dashboard-reference.xlsx` |
| PowerPoint `.pptx` | **IC monthly deck** (35+ slides — slide-19 ratios, slides 17-26 DAT sell+call, slide-27 structured-loan book) | ✅ **template exists** | `config/templates/ic/IC-meeting-deck-reference.pptx` |
| Generation contract | `config/templates/ic/meeting-templates.json` — field map for all 3 artefacts | ✅ exists | the canonical I/O mapping |

> **IC is the most complete in terms of templates.** Logical next dept to fully scaffold end-to-end (the chair-function 3-artefact pipeline). Should be ~half a day's work.

---

## 4. VCC — Singapore VCC (Brook Technology Capital VCC)
`capabilityTier: write_via_staging` (confidence ≥ 0.90)

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | Quarterly LP report (TVPI / DPI / IRR per sub-fund, capital called, distributions) | 🟡 | needs Formidium NAV as input |
| Report `.docx` | NAV reconciliation memo (internal calc vs Formidium) | 🟡 | flagged in SKILL.md escalation |
| Report `.docx` | Audit-prep memo for Ernst & Young | 📝 | implied by FY2026 audit cycle |
| Excel `.xlsx` | NAV tracker (per sub-fund × per period) | 🟡 | staging path; needs schema |
| Excel `.xlsx` | LP register / commitment schedule | 🟡 | flagged sensitive — aggregate/anonymise per SKILL |
| Excel `.xlsx` | Service-provider fee schedule (Formidium / Ternary / Hex Trust / EY) | 🟡 | from signed amendments |
| PowerPoint `.pptx` | LP investor deck (`Brook Limited Partners FoF_I_Full_Deck_HemrajVersion.pptx` template) | ✅ **template exists** | `config/templates/vcc/vcc-deck-template.pptx` |
| PowerPoint `.pptx` | Annual LPAC presentation | 📝 | implied — fund manager standard |

---

## 5. Legal & Compliance
`capabilityTier: read_only`

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | PE risk assessment memo (Timblick-style — per onshore activity proposal) | 🟡 | `[2025-12-29-thai-regulatory-tax-opinion]` is the pattern |
| Report `.docx` | Engagement scope review (whenever a non-Timblick legal q comes up) | 🟡 | `[2026-03-23-law-studios-engagement-...]` is the template |
| Report `.docx` | Contract review memo (HT Markets MTA style) | 🟡 | `HT_Markets_MTA_Review_Memo.docx` |
| Excel `.xlsx` | Compliance tracker (filings due, status, owner) | 📝 | predecessor `Compliance_Tracker.xlsx` was un-grounded; build fresh |
| Excel `.xlsx` | Contract renewal register | 📝 | implied — currently nothing for SCB/BBL/Hex Trust renewal dates |
| PowerPoint `.pptx` | Quarterly legal & compliance update to Board | 🟡 | brooker template |

---

## 6. Finance / CFO (BICL)
`capabilityTier: write_via_staging`

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | BICL audited-statement prep memo (FY-end notes-to-financials) | 🟡 | from BICL FY2025 audit pattern |
| Report `.docx` | Related-party loan exposure memo (PN.34/35/36 aggregate) | 🟡 | quoteable from the PN decision logs |
| Report `.docx` | FATCA / W-8BEN-E status memo (annual refresh) | 🟡 | new doc each renewal cycle |
| Report `.docx` | Quarterly CFO board pack (alongside or merged with CAC report) | 🟡 | could re-use CAC report mechanic |
| Excel `.xlsx` | BICL trial balance (monthly) | 📝 | implied for audit prep |
| Excel `.xlsx` | PN amortization schedule | 📝 | implied — interest accrual on PN.34/35/36 |
| Excel `.xlsx` | Intercompany loan tracker (BG ↔ BICL) | 📝 | parent-sub exposure |
| PowerPoint `.pptx` | Quarterly CFO update to Board | 🟡 | brooker template |

---

## 7. CEO — Board-level meta-agent
`capabilityTier: read_only` (synthesises across all depts)

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **Board pre-read pack** (enterprise posture + North Star vs OKR delta + cross-dept synthesis) | 🟡 | aggregates from every dept's monthly artefact |
| Report `.docx` | Quarterly North Star / OKR progress report | 🟡 | OKR-1...5 status report |
| Report `.docx` | Khao Yai Resolutions R-01..R-08 status memo (which decisions are in effect, which are pending) | 🟡 | governance-trail document |
| Excel `.xlsx` | **OKR tracker** (5 objectives × monthly progress) | 📝 | high-value, doesn't exist yet |
| Excel `.xlsx` | Strategic initiative timeline | 📝 | implied — Stop List + Three-Engine progress |
| PowerPoint `.pptx` | **Quarterly Board deck** (enterprise-wide synthesis — biggest deliverable per quarter) | 🟡 | brooker template, deck-writer can render |
| PowerPoint `.pptx` | Investor / Capital Markets day deck | 📝 | implied — Equity-story re-rating (R-08) |

---

## 8. Comms / IR
`capabilityTier: read_only` (drafts marked NOT FOR EXTERNAL USE)

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | Event arrangement brief (Pantera-style: agenda, RSVP plan, venue shortlist) | 🟡 | `[Pantera x Brooker April Event.docx]` template |
| Report `.docx` | IR Q&A document (anticipated questions + approved language) | 🟡 | implied; no source today — needs new corpus |
| Report `.docx` | Press release / disclosure draft (always marked DRAFT — needs Legal sign-off) | 🟡 | abstains today (no filed-disclosure corpus per Hard Rule) |
| Excel `.xlsx` | Event guest list / RSVP tracker (≤40-cap private lunch pattern) | 📝 | implied from event playbook |
| Excel `.xlsx` | IR question / response calendar | 📝 | implied |
| PowerPoint `.pptx` | **Investor event deck** (BNB Gala / Pantera-collab style) | 🟡 | `vcc-deck-template.pptx`; macro slides exist in `[chinese association slides]`, `[Pantera macro outlook]` |
| PowerPoint `.pptx` | CEO keynote slides ("Audacity of Value" pattern) | 🟡 | `[BNB $1K Gala Night CEO speech.docx]` is the script source |
| PowerPoint `.pptx` | Macro thought-leadership deck (Geopolitical Recalibration / Global Liquidity Cycle / Internet of Value) | 🟡 | from the existing macro corpus |

---

## 9. HR
`capabilityTier: read_only`; corpus is THIN (2 Thai self-assessment PDFs)

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | Control-status memo (item-by-item readout of the 10 contract-storage + 14 WFH controls) | 🟡 | direct from the 2 questionnaires |
| Report `.docx` | Annual policy review memo (WFH §23/1, contract retention) | 🟡 | basic readout |
| Excel `.xlsx` | Self-assessment questionnaire response sheet (Thai template) | 🟡 | the format itself is reusable |
| Excel `.xlsx` | Headcount tracker | ❌ deferred | NO source today (Hard Rule: refuse + flag HOD) |
| Excel `.xlsx` | Compensation / pay-equity sheet | ❌ deferred | NO source today |
| PowerPoint `.pptx` | Quarterly HR update | ❌ deferred | not enough corpus to populate |

---

## 10. Risk — EMPTY CORPUS today
`capabilityTier: read_only`

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | Risk appetite + KRI dashboard memo | ❌ deferred | needs risk policy + KRI dashboard ingested first |
| Report `.docx` | Stress-test outcome memo | ❌ deferred | needs stress framework data |
| Excel `.xlsx` | KRI dashboard | ❌ deferred | empty corpus |
| Excel `.xlsx` | Risk register | ❌ deferred | empty corpus |
| PowerPoint `.pptx` | Quarterly Risk Committee deck | ❌ deferred | empty corpus |

---

## 11. IB — EMPTY CORPUS today
`capabilityTier: read_only`

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | Term-sheet draft / deal memo | ❌ deferred | 0 chunks in ib_docs |
| Report `.docx` | Counterparty DD memo | ❌ deferred | empty corpus |
| Excel `.xlsx` | Deal pipeline tracker | ❌ deferred | empty corpus |
| Excel `.xlsx` | Covenant register (standalone — not the CAC one) | ❌ deferred | empty corpus |
| PowerPoint `.pptx` | Deal pitch deck for IC | ❌ deferred | empty corpus |

---

## 12. IT — EMPTY CORPUS today
`capabilityTier: read_only`

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | Infra availability / incident summary | ❌ deferred | 0 chunks |
| Report `.docx` | Security assessment summary (pentest, vulns) | ❌ deferred | 0 chunks |
| Excel `.xlsx` | IT budget tracker | ❌ deferred | 0 chunks |
| Excel `.xlsx` | Vulnerability register | ❌ deferred | 0 chunks |
| PowerPoint `.pptx` | Quarterly tech-health deck | ❌ deferred | 0 chunks |

---

---

## 13. Cross-cutting / system artefacts (not dept-specific)

These are produced by the system itself or by services that span depts. Not in the per-dept tables above but still real agent outputs that need tests.

| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Markdown `.md` | **Daily logs per dept** — `obsidian-vault/{dept}/daily-logs/YYYY-MM-DD.md` | 🟡 | reflection-engine nightly (12 depts × 1/day) |
| Markdown `.md` | **Memory promotion files** — `obsidian-vault/{dept}/_memory/{agent}/memory.md` rewritten from chat history | 🟡 | reflection-engine; existing files in vault confirm output shape |
| Markdown `.md` | **Skill proposals** — when recurring knowledge gaps detected, reflection drafts a new SKILL.md stub for review | 🟡 | reflection-engine + knowledge_gaps table |
| DB row | **Knowledge gap records** — postgres `knowledge_gaps` table entries flagged by `detect_self_report` | 🟡 | `services/shared/knowledge_gaps.py` |
| Email `.eml` | **Escalation emails to HODs** — fires when a metric breaches its threshold | 🟡 | `email-notifier` service + `config/escalation_rules.json` |
| Slack message | **Thread reply with citations** — every agent answer in Slack with `[N]` citations | ✅ | covered by chat-path tests; format verified |
| Slack file upload | **Artefact attachment to thread** — `.docx` / `.pptx` files uploaded via `responder._upload_artefact` | ✅ | covered by CAC report e2e |
| DB row + archive | **Approval audit trail** — `staging_proposals` table + approved-version archive `.docx` | 🟡 | approval-ui → postgres + `/data/archive/{dept}/` |
| File copy | **Sync-back archive** — approved staging xlsx copied to mirror and to `/data/archive/{dept}/YYYY-MM-DD/` | 🟡 | `sync-back` service |
| Slack message | **Cross-dept escalation notification** — CAC liquidity breach notifies `#risk-committee` | 🟡 | slack-bot escalation channel post |
| HTTP response | **Cross-dept handoff via `read_collections` cross-read** — e.g. CAC pulling `finance_docs` in retrieve_context | ✅ | covered by retrieval round-robin tests |
| `.docx` | **Compaction summary** when chat context exceeds budget | 📝 | LangGraph saver behavior |
| Log file | **Daily reflection write to log.md** — `obsidian-vault/{dept}/log.md` rolling summary | 🟡 | reflection-engine |

---

## 14. Per-dept additional artefacts (second pass — were missed in §1–§12)

### CAC additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **ALCO meeting minutes** (separate from the Monthly Report — committee decision log per meeting) | 🟡 | per CAC SKILL.md mandate |
| Excel `.xlsx` | **Cost-of-funds (COF) calculation sheet** — weighted-average debt rate by facility | 🟡 | per SKILL Hard Rule on COF tracking |
| Excel `.xlsx` | Funding-mix sheet (bank __% / on-chain __% / bond __% / equity __%) | 🟡 | column in CAC Data Pack section 4 |

### CIO additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **BBD / BitcoinMiner Thailand** operations update memo (70 MB pilot status, ACE/UBON sites) | 🟡 | `[Mining Summary.pptx]` source pattern |
| Excel `.xlsx` | **BSFL Monthly MTM sheet** — `BSFL Monthly 2604xx.xlsx` series; SET-listed Thai equities NVDR/foreign | 🟡 | existing source file pattern |
| Report `.docx` | **Asian Finance (ADFIN) 5-yr plan refresh** memo | 🟡 | `[AsianFinance BOD BUSINESS PLAN (15 DEC 2025).pdf]` pattern; flat at Bt 185M |
| Report `.docx` | **Portfolio rebalancing recommendation** (Engine-3 sell-down sizing) | 🟡 | tied to `[dat-sell-call-strategy]` |

### IC additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **DD pipeline status report** (BICL Movie / a16z / Pantera / yield-FoF candidates) | 🟡 | per IC SKILL.md "live DD pipeline" section |
| Excel `.xlsx` | **Concentration / Red-Flag standing dashboard** (separate from main IC dashboard) | 🟡 | tracks MILL/Wave/B/PACE/CV drawdowns |
| Report `.docx` | **DAT sell+call execution playbook** — TWAP + Short Call sizing per month (strikes / premia) | 🟡 | per `[dat-sell-call-strategy]` deck slides 17-26 |

### VCC additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Excel `.xlsx` | **Closing batch log** — record of subscription cut-off per closing | 🟡 | explicitly named in VCC SKILL.md staging-proposal section |
| Excel `.xlsx` | **GP commit tracker** — running record of ~$11.2M GP/anchor commitment evolution | 🟡 | per SKILL |
| Report `.docx` | **Defaulting-investor admin-charge record** (10% Administrative Charge per FoF I Supplement) | 🟡 | per Supplement defaulting-investor clause |

### Legal additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **Form 56-1 Thai SEC annual disclosure prep memo** | 🟡 | listed company obligation; no corpus today |
| Report `.docx` | **AML / sanctions screening output** (for new counterparty / LP onboarding) | 📝 | implied — VCC subscribers + IB counterparties |
| Report `.docx` | **KYC review** for new counterparty (Hex Trust restricted-jurisdiction check + UBO review) | 🟡 | per CIO SKILL.md cross-read; legal sign-off needed |

### Finance additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **Monthly closing memo** — BICL FY-close commentary | 📝 | implied by audit cycle |
| Excel `.xlsx` | **Cash-flow statement** — deterministic from accounting data | 📝 | implied for full BICL trial balance package |
| Report `.docx` | **Transfer-pricing intercompany documentation** | 📝 | implied — BG ↔ BICL PNs need TP support |

### CEO additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **M&A pipeline review** (if/when applicable) | 📝 | implied — Three-Engine flywheel includes acquisition optionality |
| Excel `.xlsx` | **Capital-allocation decisions log** — running record per R-05 Decision Rights Matrix | 🟡 | per CEO SKILL.md governance role |
| Report `.docx` | **5-year retrospective updates** (analogue of `[five-year-retrospective-2021-2025]`) | 🟡 | existing wiki article is the pattern |

### Comms additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| Report `.docx` | **Investor one-pager** — standing fund / firm summary for prospects | 📝 | implied IR collateral |
| Report `.md` | **Brand asset library record** — logos / palette / fonts inventory | 📝 | partial — palette HEX values are in SKILL.md |
| Report `.docx` | **CEO speech transcripts** (post-event archive) — `[BNB $1K Gala Night CEO speech.docx]` precedent | 🟡 | one exists; pattern for future events |

### HR additions
| Type | Deliverable | Status | Source / How |
|---|---|---|---|
| PowerPoint `.pptx` | **Org chart** | ❌ deferred | no current source data |
| Excel `.xlsx` | **Training tracker** — control item #6 of contract-storage questionnaire ("Labour law & ethics training") | 🟡 | partial — questionnaire confirms training "Present", but no tracker data |
| Report `.md` | **Onboarding checklist** | ❌ deferred | no current source |

### Risk / IB / IT — additions (all ❌ deferred until corpora exist)
| Dept | Missed artefacts |
|---|---|
| Risk | covenant-breach memo · capital-adequacy memo · early-warning indicator (EWI) tracker · concentration-risk heatmap |
| IB | term-sheet template library · signing checklist · KYC log · counterparty-onboarding tracker · deal pipeline kanban |
| IT | change-request log · MFA-enrolment tracker · vendor security-review log · incident post-mortems · BCP-DR test report |

---

# Headline tally (after second-pass additions)

| Status | Count | Notes |
|---|---:|---|
| ✅ Done end-to-end (verified this session) | **1** | CAC Monthly Report `.docx` (deterministic, content verified) |
| ✅ Template exists, pipeline not yet built | **4** | IC minutes / IC dashboard / IC deck / VCC deck |
| ✅ Plumbing already verified (covered by other tests) | **3** | Slack thread reply with citations · file-upload attachment · cross-dept retrieval via cross_read |
| 🟡 Mentioned in SKILL.md, scaffolding needed | **68** | dept-specific reports + xlsx + decks per §1–§9 + §14 |
| 📝 Implied by responsibility, no template yet | **20** | gap-filling artefacts surfaced in §14 |
| ❌ Deferred — corpus empty | **21** | Risk + IB + IT entirely; HR comp/headcount + a few others |
| **TOTAL distinct artefact types tracked** | **~120** | across 12 depts + 1 cross-cutting/system section (§13) |

Plus a consolidated row at the bottom of §14 enumerating **14 additional** Risk/IB/IT artefacts that fall under "deferred" — actual deferred count is closer to **35**.

Net e2e-verifiable coverage **today: 8 of ~120 (~7%)**. The rest is the build queue.

# Priority order if I were ranking what to build next

Top tier — high leverage / low risk / templates or patterns already exist:

1. **IC chair-function pipeline** (`.docx` minutes + `.xlsx` dashboard + `.pptx` deck) — all 3 templates exist + `meeting-templates.json` field-map committed. Mirrors CAC report. **~half-day**.
2. **CAC ALCO Tracker staging proposals** (`.xlsx`) — exercises `staging_writer.py` end-to-end. **Highest-priority** safety verification — only path that writes to real corporate data.
3. **CEO Quarterly Board deck** (`.pptx`) — biggest single artefact per quarter; deck-writer `/compose` wired, unexercised.
4. **VCC quarterly LP report** (`.docx`) — fund-side legal artefact; Supplement-governed.
5. **Finance + CFO quarterly board pack** (`.docx`) — possibly merge with #1's CAC report.
6. **Legal contract review memo** (`.docx`) — HT Markets MTA pattern; useful when SCB/BBL renewals come up.
7. **Comms event brief + investor event deck** — Pantera-style recurring events; corpus has patterns.

Second tier — useful system-layer artefacts (from §13):

8. **Daily logs + memory promotions** (reflection-engine output verification) — currently fire nightly but format/content not test-asserted.
9. **Escalation email** (`.eml`) — verify trigger when D/E / DTV / runway breaches limits.
10. **Approval audit trail** — verify approve/reject in approval-ui writes the right postgres row + archive copy.
11. **Cross-dept escalation notification** (CAC → `#risk-committee` Slack post).

Third tier — corpus-dependent, deferred until data arrives:

- HR comp/headcount/training trackers
- Risk KRI dashboard + appetite-breach memo + stress-test pack
- IB deal pipeline + term-sheet templates
- IT infra/security/devops dashboards

# Pipeline mapping (where each artefact type lives in code)

| Artefact type | Producing service | Endpoint | Format library | Storage path |
|---|---|---|---|---|
| Report `.docx` (deterministic from data) | deck-writer | `/report/cac-meeting` (extensible to `/report/ic-minutes`, `/report/vcc-lp`, …) | `python-docx` + `services/shared/cac_report_docx.py` pattern | `/data/reports/{name}.docx` |
| Report `.docx` (RAG-based) | deck-writer | `/report` | `python-docx` + LLM | `/data/reports/{name}.docx` |
| Excel `.xlsx` proposals (staging) | each agent's orchestrator | proposal manifest → `staging_writer.py` | `openpyxl` | `/data/staging/pending/{chg_id}.xlsx` + `.json` manifest |
| PowerPoint `.pptx` | deck-writer | `/compose` | `python-pptx` + dept template | `/data/decks/{name}.pptx` |

**Today only 2 of these 4 paths are stress-tested**: report-docx (deterministic, via CAC) and the file-upload-to-Slack mechanic. The other 2 (xlsx-staging-write and pptx-compose) need a focused test pass.
