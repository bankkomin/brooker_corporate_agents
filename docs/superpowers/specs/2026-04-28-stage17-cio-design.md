# Stage 17 — CIO Office Department Implementation

**Source:** `config/departments.json#cio` + `config/document_inventory.json` (rows where `ownerDept = "cio"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — fresh design (no existing scaffold)
**Posture:** `capabilityTier: write` — NAV trackers updated cell-by-cell via staging
**Cross-read access:** finance, vcc, ic — fund / NAV cross-reference reach
**Existing scaffold:** ❌ none — fresh skill folder created at Stage 10
**Dependencies:** Stage 11 (Finance) MUST be live; Stage 16 (IC) recommended live for IC cross-read

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `cio-agent` | Orchestrator — Chief Investment Officer | `skills/cio/cio-agent.md` |
| `fund-performance-agent` | NAV reports, performance attribution per fund | `skills/cio/fund-performance.md` |
| `custody-agent` | Custodian docs, reconciliation, settlement | `skills/cio/custody.md` |
| `ppm-agent` | PPM authoring + maintenance per fund | `skills/cio/ppm.md` |

**Deviations:** None on count.

## 2. Documents Owned

```yaml
docs:
  - doc_cio_nav_reports                # NAV reports (all funds) (report)
  - doc_cio_ppm                        # PPM (all funds) (narrative)
  - doc_cio_custodian_docs             # Custodian documents (report)
```

## 3. Custom LangGraph Nodes

Possible custom node `custodian_check` after `specialist_agent` for fund-performance and custody queries — verifies NAV proposals against latest custodian statement before staging. Decision deferred to Stage 17 kickoff.

## 4. Escalation Rules

```yaml
nav_discrepancy:
  trigger: NAV proposal differs from custodian statement by > tolerance
  severity: critical
  notify: [hod_email, slack_channel, cfo_agent, risk_agent]

custodian_reconciliation_failed:
  trigger: monthly reconciliation fails for any fund
  severity: high
  notify: [hod_email, slack_channel]

ppm_amendment_required:
  trigger: regulatory or fund structure change requires PPM update
  severity: medium
  notify: [hod_email, slack_channel, legal_agent]
```

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 7 * * *"            # daily 07:00 — overnight NAV positions
  context_sources: ["sharepoint:CIO/NAV", "sharepoint:CIO/Custody", "slack:#cio-committee"]
  outbound_actions: ["draft_email", "post_slack_summary"]
```

Activate after 30d post-go-live. Use case: morning NAV summary email to fund admin team.

## 6. Per-skill Permission Overrides

| Skill | Override | Reason |
|---|---|---|
| `skills/cio/custody.md` | `data_zones: [1]` (read-only on Zone 2 even though dept is write-capable) | Custodian data is reference-only; agent must not propose edits to custody-side records |

Other skills use dept-default permissions (`mode: write_via_staging`, `data_zones: [1, 2]`, `outbound_apis: []`, `read_collections: [cio_docs, cio_chat, cio_knowledge, shared_policies, finance_docs, vcc_docs, ic_docs]`).

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#cio-committee` |
| HOD email | (added at kickoff) |
| Approval-UI route | `/cio/dashboard` |
| Service port | 3016 |

## 8. Out of Scope

- Trade execution (CIO advises; portfolio managers execute)
- Direct integration with custody platforms (read from sync-mirror only)
- Per-fund granular dashboard (Stage 17 ships single CIO dashboard; per-fund can be Stage 17.5)
- Heartbeat (deferred per §5)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] Cross-read works: CIO Agent retrieves from `finance_docs` (always) and `vcc_docs` / `ic_docs` if those stages are live
- [ ] NAV staging proposal flow: agent proposes value → HOD email → approval-ui → approve → sync-back writes to NAV tracker mirror
- [ ] Custody-agent skill enforces `data_zones: [1]` override (verified via integration test)
- [ ] PPM update queries surface latest version from `cio_docs`
- [ ] VCC Agent (post Stage 18) can RAG-retrieve from `cio_docs` for fund alignment

## 10. Rollback Plan

If stage fails post-deploy: `live: false`, restart gateway. VCC Stage 18 dependency on `cio_docs` reverts to graceful-degrade mode. No data destruction.
