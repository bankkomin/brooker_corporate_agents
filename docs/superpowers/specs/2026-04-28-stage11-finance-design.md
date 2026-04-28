# Stage 11 — Finance Department Implementation

**Source:** `config/departments.json#finance` + `config/document_inventory.json` (rows where `ownerDept = "finance"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — to be fleshed out at Stage 11 kickoff
**Posture:** `capabilityTier: write` — Finance is the first Phase 2 write-capable dept; stress-tests cross-dept read enforcement and staging gate
**Cross-read access:** own + `shared_policies` only (read-side; many other depts cross-read INTO Finance)

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `cfo-agent` | Orchestrator — financial reporting umbrella | `skills/finance/cfo-agent.md` |
| `reporting-agent` | Annual report, Financial statements & notes | `skills/finance/reporting.md` |
| `treasury-agent` | Networth report, BG/Coins weekly cash positions | `skills/finance/treasury.md` |
| `mda-agent` | MD&A drafting (cross-published with CEO) | `skills/finance/mda.md` |

**Deviations from default 4-agent shape:** None on count. Note: `skills/shared/cfo-agent.md` already exists in repo (used by CAC); migrate to `skills/finance/cfo-agent.md` and leave a thin re-export stub in `shared/` for one stage as backwards compat.

## 2. Documents Owned

```yaml
docs:
  - doc_finance_annual_report          # Annual report (report)
  - doc_finance_statements_notes       # Financial statements & notes (report)
  - doc_finance_networth_report        # Networth report (report)
  - doc_finance_bg_weekly              # BG weekly/monthly report (report)
  - doc_finance_coins_weekly           # Coins weekly/monthly report (report)
```

## 3. Custom LangGraph Nodes

None — uses standard graph from framework §4.1.

## 4. Escalation Rules

TBD at Stage 11 kickoff. Likely candidates:

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

Final values from CFO + treasury policy at kickoff.

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 8 * * 1"           # Mondays 08:00, weekly Networth reminder
  context_sources: ["sharepoint:Finance/Networth", "slack:#finance-committee"]
  outbound_actions: ["draft_email", "post_slack_summary"]
```

Activate after 30d post-go-live. Initial use case: weekly Networth update reminder + draft of summary email to CEO.

## 6. Per-skill Permission Overrides

All skills use dept-default permissions (`mode: write_via_staging`, `data_zones: [1, 2]`, `outbound_apis: []`, `read_collections: [finance_docs, finance_chat, finance_knowledge, shared_policies]`).

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#finance-committee` |
| HOD email | (added to `config/hod_emails.json` at Stage 11 kickoff) |
| Approval-UI route | `/finance/dashboard` |
| Service port | 3010 |

## 8. Out of Scope

- Tax / audit specialist agent (separate dept-extension request)
- Heartbeat (deferred per §5)
- Direct integration with external ERP system (read from sync-mirror only)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass (per framework §5 Step 11)
- [ ] **CAC's CFO Agent can RAG-retrieve Finance docs** — first end-to-end test of cross-dept read with new dept (biggest architectural risk per framework §7.5)
- [ ] Networth tracker staging proposal flows: agent proposes value → HOD email → approval-ui → approve → sync-back writes to mirror
- [ ] `agent_performance` view records `signal_strength` correctly for at least one approved + one edited proposal
- [ ] Reflection engine processes Finance daily logs without error after 24h of activity

## 10. Rollback Plan

If stage fails post-deploy: `live: false` in departments.json, restart gateway, retain code on branch. CAC's `crossReadAccess` reverts to pre-Stage-11 state (no Finance reads). No data destruction.
