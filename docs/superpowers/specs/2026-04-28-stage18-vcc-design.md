# Stage 18 — VCC Department Implementation

**Source:** `config/departments.json#vcc` + `config/document_inventory.json` (rows where `ownerDept = "vcc"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — fresh design (no existing scaffold)
**Posture:** `capabilityTier: write` — NAV cells, client list updates via staging
**Cross-read access:** cio, ic — fund / IC alignment reach
**Existing scaffold:** ❌ none — fresh skill folder created at Stage 10
**Dependencies:** Stage 17 (CIO) MUST be live; Stage 16 (IC) recommended live

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `vcc-head-agent` | Orchestrator — VCC umbrella | `skills/vcc/vcc-head-agent.md` |
| `client-relations-agent` | VCC client list, presentations, contracts, due diligence | `skills/vcc/client-relations.md` |
| `nav-subs-agent` | NAV updates, subscriptions, redemptions | `skills/vcc/nav-subs.md` |
| `comms-agent` | Newsletters + investment memos for VCC clients | `skills/vcc/comms.md` |

**Deviations:** None on count. Note: `comms-agent` here is a VCC-internal agent and is distinct from the Communications dept's `comms-agent` (Stage 15) — namespacing via `dept_id` prefix prevents collision.

## 2. Documents Owned

```yaml
docs:
  - doc_vcc_client_list                # VCC client list (tracker)
  - doc_vcc_presentations              # VCC presentations (narrative)
  - doc_vcc_contracts                  # VCC contracts (narrative)
  - doc_vcc_due_diligence              # VCC due diligence (narrative)
  - doc_vcc_subscriptions              # Subscriptions (report)
  - doc_vcc_nav                        # VCC NAV (report)
  - doc_vcc_newsletters                # VCC newsletters (narrative)
  - doc_vcc_investment_memos           # VCC investment memos (narrative)
```

## 3. Custom LangGraph Nodes

Possible `kyc_check` node after `classify_intent` for client-relations queries — runs against client list to verify subject is an active VCC client before retrieval. Decision deferred to Stage 18 kickoff.

## 4. Escalation Rules

```yaml
client_subscription_anomaly:
  trigger: subscription/redemption pattern outside normal range
  severity: high
  notify: [hod_email, slack_channel, risk_agent]

contract_expiring_soon:
  trigger: VCC contract expires within 30 days
  severity: medium
  notify: [hod_email, slack_channel]

newsletter_pending:
  trigger: monthly newsletter cadence missed
  severity: low
  notify: [hod_email, slack_channel]
```

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 8 * * 1"            # Mondays 08:00 — weekly client + NAV digest
  context_sources: ["sharepoint:VCC/ClientList", "sharepoint:VCC/NAV", "slack:#vcc-committee"]
  outbound_actions: ["draft_email", "post_slack_summary"]
```

## 6. Per-skill Permission Overrides

| Skill | Override | Reason |
|---|---|---|
| `skills/vcc/client-relations.md` | `data_zones: [1, 2]` + `outbound_apis: []` | Client list updates allowed via staging; NO direct outbound (PII) |

Other skills use dept-default permissions (`mode: write_via_staging`, `data_zones: [1, 2]`, `outbound_apis: []`, `read_collections: [vcc_docs, vcc_chat, vcc_knowledge, shared_policies, cio_docs, ic_docs]`).

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#vcc-committee` |
| HOD email | (added at kickoff) |
| Approval-UI route | `/vcc/dashboard` |
| Service port | 3017 |

## 8. Out of Scope

- KYC/AML automated checks (manual today; could add `kyc_check` node in Stage 18.5)
- Direct integration with fund admin platform (read from sync-mirror)
- Newsletter publishing (drafted by agent, sent by humans through existing distribution)
- Heartbeat (deferred per §5)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] Cross-read works: VCC Agent retrieves from `cio_docs` (must be live) and `ic_docs` (if live)
- [ ] NAV staging proposal flow works (parallel to Stage 17 CIO flow but for VCC NAV)
- [ ] Client list update staging proposal flow works (rare event; tracker tier doc)
- [ ] PII handling: client-relations skill cannot trigger any outbound action (verified by integration test)
- [ ] CIO Agent (Stage 17) can RAG-retrieve from `vcc_docs` for fund alignment

## 10. Rollback Plan

If stage fails post-deploy: `live: false`, restart gateway. CIO's cross-read to `vcc_docs` graceful-degrades. No data destruction.
