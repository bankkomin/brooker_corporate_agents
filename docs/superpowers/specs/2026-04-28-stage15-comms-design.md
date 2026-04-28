# Stage 15 — Communications (IR/PR) Department Implementation

**Source:** `config/departments.json#comms` + `config/document_inventory.json` (rows where `ownerDept = "comms"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — fresh design (no existing scaffold)
**Posture:** `capabilityTier: read_only` (publishing flow is human-driven; agent advises and drafts)
**Cross-read access:** own + `shared_policies` only (standard isolation)
**Existing scaffold:** ❌ none — fresh skill folder created at Stage 15

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `comms-agent` | Orchestrator — IR/PR/Branding umbrella | `skills/comms/comms-agent.md` |
| `ir-agent` | Investor relations content + analyst tracking | `skills/comms/ir.md` |
| `pr-agent` | Press releases, media kit, earnings call decks | `skills/comms/pr.md` |
| `branding-agent` | Brand guidelines, marketing collateral, web/social copy | `skills/comms/branding.md` |

**Deviations:** None on count. Note: branding team rolls up under Comms per org chart update (2026-04-28). Branding policy moved from HR to Comms in `document_inventory.json` and org chart diagram at Stage 10.

## 2. Documents Owned

```yaml
docs:
  - doc_comms_branding_policy          # Branding policy (policy)
  - doc_comms_brand_guidelines         # Brand guidelines (policy)
  - doc_comms_press_releases           # Press releases & media kit (narrative)
  - doc_comms_ir_newsletters           # Investor newsletters (narrative)
  - doc_comms_earnings_decks           # Earnings call decks (narrative)
  - doc_comms_web_social               # Website / social copy (narrative)
  - doc_comms_marketing_collateral     # Marketing collateral (narrative)
```

## 3. Custom LangGraph Nodes

None — uses standard graph from framework §4.1.

## 4. Escalation Rules

```yaml
brand_guideline_breach:
  trigger: proposed external content violates brand guideline
  severity: medium
  notify: [hod_email, slack_channel]

ir_disclosure_concern:
  trigger: proposed IR content includes potentially material non-public information
  severity: critical
  notify: [hod_email, slack_channel, legal_agent, ceo_agent]
```

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 8 * * 1"            # Mondays 08:00 — weekly IR/PR pipeline digest
  context_sources: ["sharepoint:Comms/Pipeline", "slack:#comms-committee"]
  outbound_actions: ["post_slack_summary"]
```

Read-only dept — drafting + outbound publishing requires human approval (Comms team owns Hootsuite / Gmail / etc.). Heartbeat just summarises pipeline.

## 6. Per-skill Permission Overrides

All skills use dept-default permissions (`mode: read_only`, `data_zones: [1]`, `outbound_apis: []`, `read_collections: [comms_docs, comms_chat, comms_knowledge, shared_policies]`).

**IR Agent special note:** may receive crossRead to `finance_docs` post-Stage-11 to enable IR content fact-checks against latest financials. Decision deferred to Stage 15 kickoff.

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#comms-committee` |
| HOD email | (added at kickoff) |
| Approval-UI route | `/comms/dashboard` (read-only — query + draft history) |
| Service port | 3014 |

## 8. Out of Scope

- Direct posting to external channels (Twitter/LinkedIn/email — humans do)
- Direct integration with PR distribution services (PR Newswire, Business Wire, etc.)
- Image generation / video editing (separate skill bundle, not part of this stage)
- Heartbeat (deferred per §5)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] Read-only enforcement: `staging_writer` node absent from compiled graph
- [ ] Branding policy query returns citation from `comms_docs` (verifies relocation from HR worked)
- [ ] HR no longer surfaces Branding policy in its retrieval (verifies removal from `hr` ownership)
- [ ] CEO Agent (which has cross-read all) can retrieve from `comms_docs` for MD&A drafting

## 10. Rollback Plan

If stage fails post-deploy: `live: false`, restart gateway. Branding policy ownership rollback to HR is configurable but expected to stay with Comms (org-chart change is independent of code rollback). No data destruction.
