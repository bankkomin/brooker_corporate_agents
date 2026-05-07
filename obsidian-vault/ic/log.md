---
title: "IC Operations Log"
type: log
department: "ic"
---

## [2026-04-07] init | Wiki knowledge base initialized for ic department (folder skeleton)

## [2026-05-06] seed | One-shot ingest from 3 sample IC meeting docs + Feb 2026 dashboard

Sources:
- `IC 01 meeting Jan2025.docx` → [[IC-2025-01-23]]
- `IC 02 meeting Mar2025.docx` → [[IC-2025-04-02]] (actual meeting date 2 Apr 2025)
- `IC 01 meeting Feb2026.docx` → [[IC-2026-03-19]] (actual meeting date 19 Mar 2026; reviews [[dashboard-2026-02]])
- `Dashboard Feb2026.xlsx` → [[dashboard-2026-02]]

Files created:
- 4 concepts (`red-flag-policy`, `concentration-policy`, `investment-holding-limit`, `liquidity-management-policy`)
- 10 decisions (running objectives, see [[index]])
- 16 entities (Listed, Non-Listed, Digital, Structured Loan portfolio)
- 2 trends (`dashboard-2026-02`, `portfolio-allocation-history`)
- 3 meeting notes
- 1 template (`templates/meeting-note.md` — ignored by vault watcher per [`obsidian_watch.json`](../../config/obsidian_watch.json))

Pending follow-ups:
- Stage 16 §9 acceptance: existing `skills/ic/` content audited and merged with framework §4.9 frontmatter (still TODO)
- `obsidian-vault/invest/` legacy folder removed (this entry covers cleanup)
- `crossReadAccess` for ic in `config/departments.json` should be reviewed: spec lists `[finance, cio, vcc, legal]` but the seeded content has heavy CAC overlap (liquidity, ALCO tracker) — recommend adding `cac`

## [2026-05-06] augment | Mar 2026 IC deck ingested (`IC No1 Mar 2026.pptx`, 35 slides)

Source: `IC No1 Mar 2026.pptx` (35 slides) — augments [[IC-2026-03-19]] with macro update, engine framework, DAT sell+call strategy, prediction-market pilot, capital sovereignty doctrine, expanded structured-loan inventory, and formal Action & Approval list.

New files:
- 2 concepts: [[engine-framework]] · [[okr-500mb-recurring-income]]
- 4 decisions: [[dat-sell-call-strategy]] · [[bicl-movie-private-credit]] · [[prediction-market-pilot]] · [[capital-sovereignty-doctrine]]
- 5 loan-borrower entities: [[chill-space-areeya]] · [[wave-expo]] · [[k-viwat-areeya-owner]] · [[purple-venture-robinhood]] · [[mr-phongphan]]
- 6 partner entities: [[a16z-crypto-fund-v]] · [[pantera-fund]] · [[obsidian-creek-capital]] · [[hex-trust]] · [[fireblocks]] · [[deribit]]

Updated files:
- [[IC-2026-03-19]] — added Macro / Engine sections / Action & Approval / expanded structured-loan table
- [[structured-loan-portfolio]] — replaced with deck's canonical 12-loan inventory (was 9-loan)
- [[digital-asset-treasury-divestment]] · [[option-wheel-prediction-markets]] · [[singapore-vcc-structure]] — augmented with deck specifics

Name correction: "Mr. Ekkapong" (.docx 2025) → "Mr. Phongphan" (deck Mar 2026) — same loan, deck treated as canonical.

Pending:
- One IC deck still leaves the **Outlook section** in older meetings under-covered (only narrative + Mar 2026 deck slides 2-11). Future ingest of Jan 2025 / Apr 2025 decks would fill that gap.
- The **Sukhothai presentation appendix** is still un-ingested — Sukhothai narrative is thin in all sources.
- The **Brooker Portfolio presentation** for stock-by-stock detail is still un-ingested.

## [2026-05-06] generation-templates | IC output-generation contract added

The IC agent now has a contract for **producing** the next monthly meeting artifacts (not just reading historical ones).

New files:
- `obsidian-vault/ic/templates/meeting-minutes-docx.md` — DOCX schema (section/table/placeholder map)
- `obsidian-vault/ic/templates/meeting-deck-pptx.md` — PPTX schema (35-slide content map)
- `config/templates/ic/meeting-templates.json` — single source of truth: vault → docx field → pptx slide mapping, output paths, approval workflow
- `config/templates/ic/IC-meeting-minutes-reference.docx` — style/structure reference (Feb 2026 minutes)
- `config/templates/ic/IC-meeting-deck-reference.pptx` — style/structure reference (Mar 2026 deck)
- `config/templates/ic/IC-dashboard-reference.xlsx` — dashboard schema reference (Feb 2026)

Updated:
- `skills/ic/ic-chair-agent.md` — frontmatter now declares `mode: read_only_with_staging_drafts` and `data_zones: [1, 2]`; added "Output Generation" section with the 3-companion-draft contract (markdown + docx + pptx) plus dashboard markdown twin; hard rules expanded to cover staging-only writes, "[TBD — verify]" placeholder rule for unknown values, and macro-slide carry-forward rule.
- `obsidian-vault/ic/index.md` — Templates section expanded; new "Generation contract" section pointing at `config/templates/ic/`.

Generation pipeline (the agent at runtime):
1. Load latest dashboard.xlsx (input from `/data/mirror/`)
2. Generate `dashboard-{period}.md` trend file → vault
3. Resolve current status of every running `ic/decisions/*.md`
4. Render markdown meeting note → vault (RAG-indexable immediately)
5. Render docx via reference template → `/data/staging/pending/ic/`
6. Render pptx via reference template → `/data/staging/pending/ic/`
7. Surface to human approval queue via approval-ui (port 4000, `/ic/dashboard`)
8. Upon approval, sync-back service writes to corporate share + archives to `/data/archive/ic/`

## [2026-05-07] validation | Tiers 1-6 ran clean (after fixes); wiki mirror added

**Static validation results (passed):**
- Frontmatter parse: 65/65 markdown files clean
- JSON contracts: `meeting-templates.json` · `departments.json` · `obsidian_watch.json` all parse
- Wikilinks: 516 scanned, 1 remaining unresolved ([[finance/financial-statements]] — intentional Stage 11 placeholder)
- Schema consistency: 0 frontmatter violations across 6 type buckets (concept · decision_log · entity · meeting_note · trend · index/log)
- PRD §11 SKILL.md compliance: all 4 active skills have required sections (Mandate · Tone · Domain · Retrieval · Output · Hard Rules)
- Cross-references: 0 orphan entities, every running decision referenced from ≥1 meeting note
- Reference path existence: all 3 binary references + 6 spot-checked vault paths exist
- Vault-watcher dry run: 56 IC files will ingest (34 → ic_docs, 22 → ic_knowledge); index.md/log.md/templates/ correctly ignored

**Real bugs found and fixed during validation:**
1. `[[wave-w4]]` referenced from wave.md and wave-w3.md but file did not exist — created [[wave-w4]] entity stub
2. `index.md` referenced [[skills/ic/ic-orchestrator]] post-rename — updated to [[skills/ic/ic-chair-agent]]
3. Wiki mirror gap — `skills/ic/*.md` was not duplicated to `obsidian-vault/skills/ic/*.md` per the CAC/HR convention. Mirror created (5 files copied byte-equal).

**Configuration issue requiring decision (not auto-fixed):**
- All 4 IC SKILL.md files declare `cac_docs` and/or `cac_knowledge` in `read_collections`, but `config/departments.json#ic.crossReadAccess` lists only `[finance, cio, vcc, legal]`. At runtime the agent will be denied access to CAC content. Recommended fix: add `cac` to the crossReadAccess array. Awaiting human approval since `departments.json` is shared dept-wiring.

**Not yet validated:**
- Tier 7 (behavioral simulation): question bank not yet built. Highest-value remaining validation.
- Tier 8 (RAG retrieval quality): requires local Qdrant + embedding endpoint.
- Tiers 9-10 (live runtime + generation pipeline): require Stage 16 deployment.

## [2026-05-07] tier-7 live test + 4 skill bug fixes from findings

Ran a live behavioural test: "How much BTC + BNB to sell at $81k / $650 today to hit 40% rule?" The skills produced a structured answer with engine attribution, scenarios, citations, and a JSON output — but the test exposed 4 real bugs that would have caused wrong recommendations in production:

**Bugs surfaced and fixed:**

1. **Denominator confusion** — Dashboard row 32 has TWO columns that look interchangeable: col B `Total Investments` (Bt 2,925mn) and col H `Investment Company Baht` (Bt 1,706mn). The 40% rule uses col H (yields 52.23%, matches deck). Using col B yields ~89% (wildly wrong). Fixed in [[skills/ic/portfolio]] (Domain Knowledge + Hard Rule), [[skills/ic/valuation]] (Hard Rule), and [[skills/ic/ic-chair-agent]] (standing constraints + Hard Rule).

2. **BNB partial Investment-Co classification** — BNB OTC is only 50.4% classified as Investment Company (Bt 414mn / Bt 822mn). Selling Bt 1 of BNB removes only Bt 0.50 from the 40%-rule numerator. A naive 1:1 sale-impact calculation under-sizes the BNB sell by ~2×. Added classification table to [[skills/ic/valuation]] and [[skills/ic/portfolio]] (Domain Knowledge sections); added the BNB-specific Hard Rule to [[skills/ic/ic-chair-agent]].

3. **Stale-dashboard handling** — The Feb 2026 dashboard was 3 months stale at test time, with crypto having rallied 12.5% since. The skills had no recipe for "use stale baseline + fresh delta from partial source". Added the 5-step stale-data adjustment recipe to [[skills/ic/portfolio]] (Domain Knowledge), referenced from [[skills/ic/ic-chair-agent]].

4. **Per-action approval-cap cross-check** — The skills did not require checking proposed actions against the open Action & Approval list quantity caps. Recommendation Bt 531mn would have silently exceeded Action #5's "up to Bt 450mn" cap. Added cross-check table + Hard Rule to [[skills/ic/ic-chair-agent]].

5. **Default execution mode for DAT sell-down** — [[dat-sell-call-strategy]] now defaults to the deck's 29.1/70.9 BTC/BNB split with 3x overlay (the IC-voted plan), with explicit deviation criteria. Added per-coin sell sizing recipe and a worked example matching the May 2026 test scenario.

**Re-validated post-fix:**
- Sync script: drift=0 across IC dept (5 files copied, byte-equal between skills/ic/ and obsidian-vault/skills/ic/)
- All Hard Rules now PRD §11 compliant
- Worked example in [[dat-sell-call-strategy]] matches the May 2026 test answer (51 BTC + 15,579 BNB with overlay)
