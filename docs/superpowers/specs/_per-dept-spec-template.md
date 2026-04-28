# Stage {N} — {Dept Name} Department Implementation

**Source:** `config/departments.json#{dept_id}` + `config/document_inventory.json` (rows where `ownerDept = "{dept_id}"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** template — copy and fill per dept

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `{orchestrator-name}` | Orchestrator | `skills/{dept}/{orchestrator-name}.md` |
| `{specialist-1}` | {1-line scope} | `skills/{dept}/{specialist-1}.md` |
| `{specialist-2}` | {1-line scope} | `skills/{dept}/{specialist-2}.md` |
| `{specialist-3}` | {1-line scope} | `skills/{dept}/{specialist-3}.md` |

**Deviations from default 4-agent shape:** {None | "+X custom agent because..." | "−1 specialist because..."}

## 2. Documents Owned

References `document_inventory.json`. Do not duplicate doc rows here — list IDs only.

```yaml
docs:
  - doc_{dept}_{slug1}    # title (tier)
  - doc_{dept}_{slug2}    # title (tier)
```

## 3. Custom LangGraph Nodes

Default graph in framework §4.1 covers most cases. List ONLY new nodes unique to this dept.

| Node | Position in graph | Purpose |
|---|---|---|
| `{node_name}` | after {existing_node} | {1-line purpose} |

If none: write *"None — uses standard graph"*.

## 4. Escalation Rules

```yaml
{rule_name}:
  trigger: {condition}
  severity: critical|high|medium|low
  notify: [hod_email | slack_channel | both]
```

Or reference `config/escalation_rules.json#{dept}`.

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: <cron>
  context_sources: [...]
  outbound_actions: [...]
```

If disabled: one-line rationale.

## 6. Per-skill Permission Overrides

| Skill | Override | Reason |
|---|---|---|

If none: write *"All skills use dept-default permissions"*.

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#{dept}-committee` |
| HOD email | (in `config/hod_emails.json`) |
| Approval-UI route | `/{dept}/dashboard` |

## 8. Out of Scope

Anything explicitly NOT building this stage.

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass (per framework §5 Step 11)
- [ ] {dept}-specific check 1
- [ ] {dept}-specific check 2

## 10. Rollback Plan

If stage fails post-deploy: `live: false` in departments.json, restart gateway, retain code on branch. No data destruction (vault folders + Qdrant collections persist; staging proposals stay in pending).
