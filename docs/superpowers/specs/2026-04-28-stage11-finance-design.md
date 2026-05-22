# Stage 11 — Finance Department Implementation

**Source:** `config/departments.json#finance` + `config/document_inventory.json` (rows where `ownerDept = "finance"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** design — fleshed out 2026-05-18; introduces the shared investment-cluster skill set
**Posture:** `capabilityTier: write` — Finance is the first Phase 2 write-capable dept; stress-tests cross-dept read enforcement and the staging gate
**Cross-read access:** own + `shared_policies` + **`cio`** (see §3 — Finance's weekly cash / networth figures physically originate in CIO's portfolio data)

---

## 0. Summary of what this stage adds

Stage 11 onboards the Finance department **and** builds a framework extension used by three departments: a **shared investment-cluster skill set** (§2). Finance, CIO (Stage 17), and IC (Stage 16) all reason over the same valuations, NAV figures, and financial statements; rather than duplicate that domain knowledge across three departments' skill files, it is authored once in `skills/shared/investment-cluster/` and pulled in per agent via a new `shared_skills` frontmatter field.

The shared skill set is **authored in full during Stage 11**. Finance consumes it immediately; IC and CIO adopt it when their stages land.

---

## 1. Agent Topology

| Agent | Role | Skill file | `shared_skills` |
|---|---|---|---|
| `cfo-agent` | Orchestrator — financial reporting umbrella | `skills/finance/cfo-agent.md` | conventions, financial-statement-reading |
| `reporting-agent` | Annual report, financial statements, BICL audited reports | `skills/finance/reporting.md` | financial-statement-reading, valuation-methodology |
| `treasury-agent` | Cash positions, BICL bank/loan facilities; cross-reads CIO weekly portfolio data | `skills/finance/treasury.md` | financial-statement-reading |
| `mda-agent` | MD&A drafting (cross-published with CEO) | `skills/finance/mda.md` | financial-statement-reading, conventions |

**Deviations from default 4-agent shape:** None on count. Note: `skills/shared/cfo-agent.md` already exists in repo (used by CAC); migrate to `skills/finance/cfo-agent.md` and leave a thin re-export stub in `shared/` for one stage as backwards compat.

`shared_skills` values above are short names; their full paths are `shared/investment-cluster/{name}` per §2.2.

## 2. Shared Investment-Cluster Skill Set (framework extension)

### 2.1 Rationale

The corporate database (`O:\brooker_database`) confirms Finance, CIO, and IC are a tightly coupled cluster:

- The **Investment Policy** (`cio/NEW INVESTMENT POLICY Feb 2024.doc`, inventoried `doc_cio_investment_policy`) is the governing document for all three — `crossReadAccess: [ic, ceo, finance, legal]`.
- **CIO owns the live valuation data** — `cio/portfolio/` holds the weekly BG listed-portfolio sheets, Coin Weekly reports, BSFL monthly portfolios, and `NET WORTH EVERY QUARTER` — all cross-read by `ic` and `finance`.
- **IC meeting minutes/decks** (`doc_ic_*`) cross-read into `finance, cio, vcc, legal`.
- **Finance's BICL audited reports & loan agreements** cross-read into `ic`.

The three departments answer questions over the same valuations, NAV figures, and statements. The domain knowledge for *how to read and reason about* those artifacts belongs in one place, not copied three ways.

### 2.2 Location & files

New directory `skills/shared/investment-cluster/`, beside the existing pan-department `skills/shared/*` files. The subdirectory namespaces these as cluster-scoped (3 departments), distinct from pan-department shared skills (citation-format, escalation-protocol):

| File | Covers | Grounded in |
|---|---|---|
| `valuation-methodology.md` | Mark-to-market, listed vs. non-listed holdings, comparables, valuation of mining/digital-asset positions | Weekly BG, BSFL monthly, Mining Summary |
| `nav-fund-accounting.md` | NAV calculation, subscriptions/redemptions, fund accounting conventions | CIO/VCC NAV reports, BSFL monthly |
| `financial-statement-reading.md` | Interpreting statements, notes, ratios; audited-report structure | BICL audited reports, Annual Report |
| `investment-cluster-conventions.md` | Shared escalation thresholds, citation style, cross-department reasoning conventions for the cluster | Investment Policy, IC minutes |

### 2.3 Loading — frontmatter declaration

SKILL.md frontmatter gains an optional `shared_skills` field — a list of skill paths (relative to `skills/`):

```yaml
---
name: reporting-agent
agent: reporting-agent
dept: finance
permissions:
  mode: write_via_staging
  data_zones: [1, 2]
  outbound_apis: []
  read_collections: [finance_docs, finance_chat, finance_knowledge, shared_policies, cio_docs]
shared_skills:
  - shared/investment-cluster/financial-statement-reading
  - shared/investment-cluster/valuation-methodology
---
```

`SkillsLoader` loads the agent's own skill, then loads each `shared_skills` entry and concatenates its **body** (frontmatter stripped) into the assembled skill content. Order: shared skills first (foundational domain knowledge), department skill last. Missing/unresolvable references are a hard error at boot (caught earlier by validation — see §2.5).

### 2.4 Permission safety — the content-only rule

**Shared skills carry no permission grants.** This is the core safety invariant:

- Each shared skill file declares frontmatter `permissions.mode: read_only` and `outbound_apis: []`.
- `SkillsLoader` merges only the **body** of a shared skill — never its frontmatter `permissions` block.
- The consuming agent's own SKILL.md frontmatter remains the **single source of truth** for `mode`, `data_zones`, and `outbound_apis`.

Consequence: a read-only IC agent (Stage 16) stays read-only even when it loads `valuation-methodology` — the same file that Finance's write-capable `reporting-agent` also loads. The shared skill contributes domain knowledge, not capability.

### 2.5 Validation

`scripts/validate_skills.py` is extended to:

- Resolve every `shared_skills` entry to an existing file under `skills/`; fail if any reference is dangling.
- Assert every file under `skills/shared/investment-cluster/` declares `permissions.mode: read_only` and `outbound_apis: []`.

### 2.6 Downstream adoption (not built in Stage 11)

- **Stage 16 (IC):** refactor the existing `skills/ic/valuation.md`, `portfolio.md`, `due-diligence.md` to declare the cluster `shared_skills` instead of carrying duplicated domain prose.
- **Stage 17 (CIO):** CIO agents declare the cluster `shared_skills` from the start.

The four shared files are authored once, now, in Stage 11.

### 2.7 Framework changes introduced by this stage

This stage extends framework artifacts from Stage 10:

- SKILL.md frontmatter schema — new optional `shared_skills` list field (extends framework §4.9).
- `SkillsLoader` (`services/shared/`) — resolve + concatenate `shared_skills` bodies; permission-merge stays own-frontmatter-only.
- `scripts/validate_skills.py` — the §2.5 checks.
- `skills/_template/` — template SKILL.md files gain a commented-out `shared_skills` example.

A back-reference should be added to the framework spec §4.9 noting `shared_skills` as a later extension.

## 3. Documents Owned & Cross-Read

### 3.1 Documents owned by Finance

Per `config/document_inventory.json` (`ownerDept = "finance"`), after the §3.3 cleanup:

```yaml
docs:
  # Reports
  - doc_finance_annual_report          # Annual Report (report)
  - doc_finance_financial_statements   # Financial Statements (report)
  - doc_finance_audited_report_2024    # BICL Audited Report 31 Dec 2024 (report)
  - doc_finance_audited_report_2025    # BICL Audited Report 31 Dec 2025 (report)
  # BICL corporate / policy
  - doc_finance_bicl_certificate_incorporation
  - doc_finance_bicl_memorandum_articles
  - doc_finance_bicl_register_directors
  - doc_finance_bicl_register_members
  - doc_finance_bicl_w8bene
  - doc_finance_bicl_address_proof
  # Loan agreements
  - doc_finance_loan_pn35              # Loan PN.35 — USD 39.02M
  - doc_finance_loan_pn36              # Loan PN.36 — USD 2.3M
  # Reimbursement / travel
  - doc_finance_travel_emirates_ticket
  - doc_finance_travel_hotel_confirmation
```

### 3.2 Cross-read into CIO

Finance's weekly cash positions, BG/Coins figures, and quarterly networth physically originate in CIO's portfolio data (`cio/portfolio/`, inventoried as `doc_cio_weekly_bg_portfolio`, `doc_cio_coin_weekly_report`, `doc_cio_net_worth_quarterly`). Finance obtains them by **cross-reading `cio_docs`**, not by owning placeholder copies.

`config/departments.json` change: `finance.crossReadAccess: ["cio"]` (was `[]`).

This is a deliberate, documented deviation from the framework §3.4 default ("Finance — own + shared only"). Rationale: the data genuinely lives in CIO. Until CIO is live (Stage 17), the framework's graceful-degradation rule (§3.5) means `cio_docs` simply returns zero hits — no error.

### 3.3 Inventory cleanup

The Stage-10 placeholder rows `doc_finance_networth_report`, `doc_finance_bg_weekly`, and `doc_finance_coins_weekly` point at non-existent `sharepoint://Finance/Weekly` sources and duplicate real CIO-owned files. **Remove these three rows** from `config/document_inventory.json`.

## 4. Custom LangGraph Nodes

None — uses the standard graph from framework §4.1. `SkillsLoader` changes (§2.3) are loader-level, not graph nodes.

## 5. Escalation Rules

Proposed defaults; final thresholds confirmed with CFO + treasury policy at implementation:

```yaml
networth_drop:
  trigger: networth declines > 10% week-over-week
  severity: high
  notify: [hod_email, slack_channel]

cash_position_critical:
  trigger: BG/Coins cash position falls below internal threshold
  severity: critical
  notify: [hod_email, slack_channel, ceo_agent]
```

## 6. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 8 * * 1"           # Mondays 08:00, weekly Networth reminder
  context_sources: ["sharepoint:Finance/Networth", "slack:#finance-committee"]
  outbound_actions: ["draft_email", "post_slack_summary"]
```

Activate after 30d post-go-live. Initial use case: weekly Networth update reminder + draft summary email to CEO.

## 7. Per-skill Permission Overrides

All Finance skills use dept-default permissions:

```yaml
mode: write_via_staging
data_zones: [1, 2]
outbound_apis: []
read_collections: [finance_docs, finance_chat, finance_knowledge, shared_policies, cio_docs]
```

Note `cio_docs` is included in `read_collections` per §3.2. The four `skills/shared/investment-cluster/*` files themselves are `mode: read_only` (§2.4) — they grant no capability.

## 8. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#finance-committee` |
| HOD email | (added to `config/hod_emails.json` at implementation) |
| Approval-UI route | `/finance/dashboard` |
| Service port | 3010 |

## 9. Out of Scope

- Tax / audit specialist agent (separate dept-extension request)
- Heartbeat activation (deferred per §6)
- Direct integration with external ERP system (read from sync-mirror only)
- Refactoring IC/CIO skills onto the shared cluster — those land in Stages 16/17 (§2.6)

## 10. Acceptance Criteria

- [ ] All 6 framework smoke tests pass (per framework §5 Step 11)
- [ ] **CAC's CFO Agent can RAG-retrieve Finance docs** — first end-to-end test of cross-dept read with a new dept (biggest architectural risk per framework §7.5)
- [ ] **Finance agents load shared investment-cluster skills** — `SkillsLoader` resolves `shared_skills`, concatenates bodies, and the agent's own permissions are unchanged by the merge
- [ ] **Content-only rule holds** — a test asserts a shared skill's frontmatter `permissions` block does not alter the consuming agent's `mode`/`outbound_apis`
- [ ] `validate_skills.py` fails a deliberately dangling `shared_skills` reference and a deliberately non-`read_only` cluster skill
- [ ] Networth/cash query resolves via cross-read of `cio_docs` (graceful zero-hit until CIO live)
- [ ] Networth-related staging proposal flows: agent proposes value → HOD email → approval-ui → approve → sync-back writes to mirror
- [ ] `agent_performance` view records `signal_strength` for at least one approved + one edited proposal
- [ ] Reflection engine processes Finance daily logs without error after 24h of activity

## 11. Rollback Plan

If the stage fails post-deploy: `live: false` for `finance` in `departments.json`, restart gateway, retain code on branch. `finance.crossReadAccess` reverts to `[]`. The `skills/shared/investment-cluster/` files are inert if no agent declares `shared_skills`, so they need not be removed. No data destruction.

## 12. Decisions Log

Recorded during the 2026-05-18 brainstorming session; all confirmed by the user.

| # | Decision | Reasoning |
|---|---|---|
| D1 | Shared skill content = valuation methodology + NAV/fund accounting + financial-statement reading + investment-cluster conventions | All four are genuine domain overlap across Finance/CIO/IC, confirmed against `O:\brooker_database` |
| D2 | Load mechanism = `shared_skills` frontmatter field; `SkillsLoader` concatenates skill bodies | Extends the existing per-skill frontmatter pattern (framework §4.9); per-agent selectivity |
| D3 | Build the shared skill set now in Stage 11 | Finance uses it immediately; IC (Stage 16) and CIO (Stage 17) adopt it later — author once |
| D4 | Location = `skills/shared/investment-cluster/` (cluster subdirectory) | Matches existing `skills/{dept}/` + `skills/shared/` convention; namespaces 3-dept-cluster vs pan-dept |
| D5 | Shared skills are content-only — no permission grants; consuming agent's own frontmatter is the sole permission source | Prevents a shared skill from widening a read-only agent's capability (lethal-trifecta surface stays per-agent) |
| D6 | Finance cross-reads CIO; drop the 3 placeholder `doc_finance_*` rows | The real BG/Coins/Networth files live in `cio/portfolio/`; placeholders pointed at non-existent sources |
