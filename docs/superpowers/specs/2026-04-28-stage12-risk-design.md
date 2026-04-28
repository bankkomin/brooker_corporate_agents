# Stage 12 — Risk Committee Department Implementation

**Source:** `config/departments.json#risk` + `config/document_inventory.json` (rows where `ownerDept = "risk"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — existing `skills/risk/` scaffold to be audited and adopted
**Posture:** `capabilityTier: read_only`
**Cross-read access:** cac, cio, finance, legal — risk surveillance reach
**Existing scaffold:** ✅ `skills/risk/` (risk-orchestrator + credit-risk + market-risk + operational-risk) — audit + adopt

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `cro-agent` | Orchestrator — risk surveillance umbrella | `skills/risk/risk-orchestrator.md` |
| `credit-risk-agent` | Credit risk monitoring | `skills/risk/credit-risk.md` |
| `market-risk-agent` | Market risk monitoring | `skills/risk/market-risk.md` |
| `operational-risk-agent` | Operational risk monitoring | `skills/risk/operational-risk.md` |

**Deviations from default 4-agent shape:** None — existing scaffold matches the standard pattern. Existing `risk-orchestrator.md` may be renamed `cro-agent.md` for naming consistency at Stage 12 kickoff.

**Audit notes:** Existing scaffold content quality reviewed at kickoff; minor updates to align with framework §4.9 permission frontmatter and §3.5 cross-dept read access.

## 2. Documents Owned

```yaml
docs:
  - doc_risk_policy                    # Risk policy (policy)
  # AML policy is co-owned with Legal — owned by legal in inventory; risk has crossRead
```

## 3. Custom LangGraph Nodes

None — uses standard graph from framework §4.1.

## 4. Escalation Rules

TBD at Stage 12 kickoff. Likely candidates align with existing CAC escalation triggers (LCR/NSFR/concentration breaches) but from risk-policy perspective.

```yaml
risk_threshold_breach:
  trigger: any threshold defined in risk policy crossed
  severity: high|critical (per policy)
  notify: [hod_email, slack_channel, ceo_agent]
```

Final rules sourced from existing risk policy doc at kickoff.

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 9 * * *"            # daily 09:00 risk dashboard digest
  context_sources: ["sharepoint:Risk/Dashboard", "slack:#risk-committee"]
  outbound_actions: ["post_slack_summary"]
```

Activate after 30d post-go-live. Read-only dept — no `draft_email` / write actions.

## 6. Per-skill Permission Overrides

All skills use dept-default permissions (`mode: read_only`, `data_zones: [1]`, `outbound_apis: []`, `read_collections: [risk_docs, risk_chat, risk_knowledge, shared_policies, cac_docs, cio_docs, finance_docs, legal_docs]`).

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#risk-committee` |
| HOD email | (added to `config/hod_emails.json` at kickoff) |
| Approval-UI route | `/risk/dashboard` (read-only — query history + escalations only) |
| Service port | 3011 |

## 8. Out of Scope

- AML policy ownership (lives with Legal; Risk has crossRead)
- Staging proposals (read-only dept; no write path compiled)
- Heartbeat (deferred per §5)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] Cross-read works: CRO Agent can retrieve from `cac_docs`, `cio_docs`, `finance_docs`, `legal_docs` per `crossReadAccess`
- [ ] Read-only enforcement: `staging_writer` node absent from compiled graph (verified via `--print-graph`)
- [ ] Existing `skills/risk/` content audited and merged with framework §4.9 frontmatter
- [ ] Risk policy queries return citations from `risk_docs` collection

## 10. Rollback Plan

If stage fails post-deploy: `live: false` in departments.json, restart gateway, retain code on branch. Other depts' `crossReadAccess` to risk reverts. No data destruction.
