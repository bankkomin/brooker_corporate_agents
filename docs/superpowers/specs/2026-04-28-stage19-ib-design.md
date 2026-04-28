# Stage 19 — Investment Banking Department Implementation

**Source:** `config/departments.json#ib` + `config/document_inventory.json` (rows where `ownerDept = "ib"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — fresh design (no existing scaffold)
**Posture:** `capabilityTier: read_only` (deal docs are narrative; structured loan report read-only for now)
**Cross-read access:** own + `shared_policies` only (standard isolation)
**Existing scaffold:** ❌ none — fresh skill folder created at Stage 10

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `ib-agent` | Orchestrator — IB deal flow umbrella | `skills/ib/ib-agent.md` |
| `deal-origination-agent` | Pitch books, target screening | `skills/ib/deal-origination.md` |
| `structuring-agent` | Term sheets, structured loan reports, transaction memos | `skills/ib/structuring.md` |
| `syndication-agent` | Syndication agreements, league tables, distribution | `skills/ib/syndication.md` |

**Deviations:** None on count. IB is the lowest-activity dept per business profile; staffing the agent topology mirrors other depts for consistency even if traffic is light.

## 2. Documents Owned

```yaml
docs:
  - doc_ib_structured_loan_report      # Structured loan report (report)
  - doc_ib_deal_docs                   # IB deal docs (narrative)
  - doc_ib_pitch_books                 # Deal pitch books (narrative)
  - doc_ib_term_sheets                 # Term sheets (narrative)
  - doc_ib_transaction_memos           # Transaction memos (narrative)
  - doc_ib_syndication_agreements      # Syndication agreements (narrative)
  - doc_ib_league_tables               # League tables (narrative)
```

## 3. Custom LangGraph Nodes

None — uses standard graph from framework §4.1.

## 4. Escalation Rules

```yaml
deal_high_risk:
  trigger: deal proposal flagged for elevated risk profile
  severity: high
  notify: [hod_email, slack_channel, risk_agent, legal_agent]

term_sheet_expiring:
  trigger: term sheet expires within 7 days without execution
  severity: medium
  notify: [hod_email, slack_channel]
```

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 9 * * 1"            # Mondays 09:00 — weekly deal pipeline digest
  context_sources: ["sharepoint:IB/Deals", "slack:#ib-committee"]
  outbound_actions: ["post_slack_summary"]
```

Read-only dept — no draft_email.

## 6. Per-skill Permission Overrides

All skills use dept-default permissions (`mode: read_only`, `data_zones: [1]`, `outbound_apis: []`, `read_collections: [ib_docs, ib_chat, ib_knowledge, shared_policies]`).

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#ib-committee` |
| HOD email | (added at kickoff) |
| Approval-UI route | `/ib/dashboard` (read-only) |
| Service port | 3018 |

## 8. Out of Scope

- Direct deal CRM integration (use sync-mirror)
- Pitch book authoring (humans draft; agent helps with research/precedent only)
- Heartbeat (deferred per §5)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] Read-only enforcement: `staging_writer` node absent
- [ ] Deal docs queries return citations from `ib_docs`
- [ ] Cross-dept escalation works: high-risk deal flagged → notification reaches risk_agent + legal_agent

## 10. Rollback Plan

If stage fails post-deploy: `live: false`, restart gateway. No data destruction. IB low-activity profile means rollback impact is minimal.
