# Stage 13 — Legal Department Implementation

**Source:** `config/departments.json#legal` + `config/document_inventory.json` (rows where `ownerDept = "legal"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — existing `skills/legal/` scaffold to be audited and adopted
**Posture:** `capabilityTier: read_only`
**Cross-read access:** **all** — contract review may touch any dept
**Existing scaffold:** ✅ `skills/legal/` (legal-orchestrator + compliance + contract-review + regulatory) — audit + adopt

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `clo-agent` | Orchestrator — legal advisory umbrella | `skills/legal/legal-orchestrator.md` |
| `compliance-agent` | Compliance monitoring (incl. AML co-owned) | `skills/legal/compliance.md` |
| `contract-review-agent` | Contract review across all depts | `skills/legal/contract-review.md` |
| `regulatory-agent` | Regulatory updates, jurisdictional changes | `skills/legal/regulatory.md` |

**Deviations:** None — existing scaffold matches standard pattern. Rename `legal-orchestrator.md` → `clo-agent.md` at kickoff for naming consistency.

## 2. Documents Owned

```yaml
docs:
  - doc_legal_opinions                 # Legal opinions (narrative)
  - doc_legal_aml_policy               # Anti-Money-Laundering policy (policy, co-owned with Risk)
  - doc_legal_contract_templates       # Contract templates (narrative)
```

## 3. Custom LangGraph Nodes

None — uses standard graph from framework §4.1.

## 4. Escalation Rules

```yaml
regulatory_change_high_impact:
  trigger: regulatory update affecting Brooker entities
  severity: high
  notify: [hod_email, slack_channel]

aml_red_flag:
  trigger: AML pattern detected in committee discussions or transaction memos
  severity: critical
  notify: [hod_email, slack_channel, ceo_agent, risk_agent]

contract_high_risk_clause:
  trigger: contract review identifies clause requiring escalation
  severity: high
  notify: [hod_email, slack_channel]
```

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 8 * * *"            # daily 08:00 — regulatory news + pending contract review queue
  context_sources: ["sharepoint:Legal/Contracts/Pending", "slack:#legal-committee"]
  outbound_actions: ["post_slack_summary"]
```

Read-only dept — no draft_email outbound.

## 6. Per-skill Permission Overrides

All skills use dept-default permissions (`mode: read_only`, `data_zones: [1]`, `outbound_apis: []`, `read_collections: ALL — see framework §3.4`).

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#legal-committee` |
| HOD email | (added at kickoff) |
| Approval-UI route | `/legal/dashboard` (read-only) |
| Service port | 3012 |

## 8. Out of Scope

- Contract drafting (read/review only; drafting goes to external counsel + scribe persona)
- Litigation case management (deferred to potential future "litigation-agent")
- Direct DocuSign integration (Stage 13 stays read-only)
- Heartbeat (deferred per §5)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] Cross-read **all-depts** works: Legal Agent can retrieve from any `*_docs` collection per `crossReadAccess: ["*"]`
- [ ] AML co-ownership works: Risk Agent and Legal Agent both surface AML policy on relevant queries (de-duplicated)
- [ ] Contract review query returns citations from cross-dept collections (e.g. asks about HR contract → retrieves from `hr_docs`)
- [ ] Existing `skills/legal/` content audited and merged with framework §4.9 frontmatter

## 10. Rollback Plan

If stage fails post-deploy: `live: false`, restart gateway. Cross-read `[*]` is the broadest read scope — verify no other dept's privacy is breached during rollback testing. No data destruction.
