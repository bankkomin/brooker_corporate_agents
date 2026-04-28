# Stage 14 — IT Department Implementation

**Source:** `config/departments.json#it` + `config/document_inventory.json` (rows where `ownerDept = "it"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — existing `skills/it/` scaffold to be audited and adopted
**Posture:** `capabilityTier: read_only`
**Cross-read access:** own + `shared_policies` only (standard isolation)
**Existing scaffold:** ✅ `skills/it/` (it-orchestrator + devops + infrastructure + security) — audit + adopt

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `cto-agent` | Orchestrator — IT operations umbrella | `skills/it/it-orchestrator.md` |
| `devops-agent` | Deployment, CI/CD, build infrastructure | `skills/it/devops.md` |
| `infrastructure-agent` | Servers, networks, capacity, monitoring | `skills/it/infrastructure.md` |
| `security-agent` | Security policies, incident response, access control | `skills/it/security.md` |

**Deviations:** None — existing scaffold matches standard pattern. Rename `it-orchestrator.md` → `cto-agent.md` at kickoff. CTO Agent already referenced in PRD §A and Stage 8 (OpenClaw supervisor); reuse that identity.

## 2. Documents Owned

```yaml
docs:
  - doc_it_policies                    # IT policies (policy)
  - doc_it_sops                        # IT SOPs (narrative)
```

## 3. Custom LangGraph Nodes

None — uses standard graph from framework §4.1.

## 4. Escalation Rules

```yaml
security_incident:
  trigger: security alert from monitoring or human report
  severity: critical
  notify: [hod_email, slack_channel, ceo_agent, legal_agent]

policy_breach_request:
  trigger: user request that would violate IT policy
  severity: medium
  notify: [hod_email, slack_channel]
```

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 7 * * *"            # daily 07:00 — overnight log digest
  context_sources: ["slack:#it-committee", "internal:openclaw_executions"]
  outbound_actions: ["post_slack_summary"]
```

Read-only dept — read-only outbound.

## 6. Per-skill Permission Overrides

All skills use dept-default permissions (`mode: read_only`, `data_zones: [1]`, `outbound_apis: []`, `read_collections: [it_docs, it_chat, it_knowledge, shared_policies]`).

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#it-committee` |
| HOD email | (added at kickoff) |
| Approval-UI route | `/it/dashboard` (read-only) |
| Service port | 3013 |

## 8. Out of Scope

- Direct deployment automation (CTO Agent advises; OpenClaw / human still execute)
- Direct AWS / Azure / on-prem write actions (read-only dept)
- Cowork plugin distribution management (handled separately by Paperclip + Stage 8 packaging)
- Heartbeat (deferred per §5)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] Read-only enforcement: `staging_writer` node absent from compiled graph
- [ ] CTO Agent identity continuity: heartbeat to Paperclip uses same agent_id as the one referenced by Stage 8 `worker_type=claude_sdk` registration (no orphaned old CTO Agent entry)
- [ ] Existing `skills/it/` content audited and merged with framework §4.9 frontmatter
- [ ] IT policy queries return citations from `it_docs` collection

## 10. Rollback Plan

If stage fails post-deploy: `live: false`, restart gateway. CTO Agent role pre-Stage-14 (Paperclip supervisor for OpenClaw, no LangGraph orchestrator) restored as fallback. No data destruction.
