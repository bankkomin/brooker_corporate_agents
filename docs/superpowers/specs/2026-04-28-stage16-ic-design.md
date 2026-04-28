# Stage 16 — IC Committee Department Implementation

**Source:** `config/departments.json#ic` + `config/document_inventory.json` (rows where `ownerDept = "ic"`)
**Pattern:** `docs/superpowers/specs/2026-04-28-stage10-phase2-framework-design.md`
**Onboarding checklist:** §5 of the framework spec
**Status:** skeleton — existing `skills/invest/` scaffold renamed to `skills/ic/` in Stage 10
**Posture:** `capabilityTier: read_only`
**Cross-read access:** finance, cio, vcc, legal — investment decisioning needs broad view
**Existing scaffold:** ✅ `skills/invest/` → renamed to `skills/ic/` in Stage 10 (ic-orchestrator + due-diligence + portfolio + valuation) — audit + adopt
**Dependencies:** Stages 11 (Finance) and 13 (Legal) MUST be live before Stage 16 — cross-read targets must exist

---

## 1. Agent Topology

| Agent | Role | Skill file |
|---|---|---|
| `ic-chair-agent` | Orchestrator — IC committee chair | `skills/ic/ic-orchestrator.md` (rename to `ic-chair-agent.md` at kickoff) |
| `due-diligence-agent` | DD packages, target screening | `skills/ic/due-diligence.md` |
| `portfolio-agent` | Portfolio review, performance tracking | `skills/ic/portfolio.md` |
| `valuation-agent` | Valuation modeling, comparables | `skills/ic/valuation.md` |

**Deviations:** None on count. Existing scaffold needs minor renames: `ic-orchestrator.md` → `ic-chair-agent.md` for consistency with `cfo-agent.md`, `cto-agent.md` etc.

## 2. Documents Owned

```yaml
docs:
  - doc_ic_investment_policy           # Investment policy (policy)
  - doc_ic_minutes                     # IC minutes & presentations (narrative)
  - doc_ic_investment_memos            # Investment memos (narrative)
```

## 3. Custom LangGraph Nodes

Possible custom node `valuation_check` after `specialist_agent` for valuation queries — runs deterministic comparable lookups against `cio_docs` before LLM synthesis. Decision deferred to Stage 16 kickoff; default = standard graph.

## 4. Escalation Rules

```yaml
investment_policy_breach:
  trigger: proposed investment violates investment policy thresholds
  severity: critical
  notify: [hod_email, slack_channel, ceo_agent, risk_agent]

new_investment_for_review:
  trigger: due-diligence package complete and ready for IC vote
  severity: medium
  notify: [hod_email, slack_channel]

portfolio_concentration_high:
  trigger: single position exceeds concentration threshold
  severity: high
  notify: [hod_email, slack_channel, risk_agent]
```

## 5. Heartbeat (opt-in)

```yaml
heartbeat:
  enabled: false
  schedule: "0 9 * * 1"            # Mondays 09:00 — IC pipeline digest
  context_sources: ["sharepoint:IC/Pipeline", "slack:#ic-committee"]
  outbound_actions: ["post_slack_summary"]
```

## 6. Per-skill Permission Overrides

All skills use dept-default permissions (`mode: read_only`, `data_zones: [1]`, `outbound_apis: []`, `read_collections: [ic_docs, ic_chat, ic_knowledge, shared_policies, finance_docs, cio_docs, vcc_docs, legal_docs]`).

**Note on cio_docs / vcc_docs:** these collections may not exist when Stage 16 ships if Stages 17/18 not yet live. Cross-read should gracefully degrade (Qdrant returns empty for missing collection); test this explicitly.

## 7. Slack & HOD config

| Field | Value |
|---|---|
| Slack channel | `#ic-committee` |
| HOD email | (added at kickoff) |
| Approval-UI route | `/ic/dashboard` (read-only) |
| Service port | 3015 |

## 8. Out of Scope

- Trade execution (read-only dept; humans execute)
- Direct integration with portfolio management systems
- Heartbeat (deferred per §5)

## 9. Acceptance Criteria

- [ ] All 6 framework smoke tests pass
- [ ] Read-only enforcement: `staging_writer` node absent
- [ ] Cross-read works for `finance_docs` and `legal_docs` (Stages 11 + 13 already live)
- [ ] Cross-read graceful degradation: missing `cio_docs` / `vcc_docs` collections do not error retrieval (returns empty hits, agent answers from available collections)
- [ ] Investment policy queries return citations from `ic_docs`
- [ ] Existing `skills/invest/` (renamed `ic/`) content audited and merged with framework §4.9 frontmatter

## 10. Rollback Plan

If stage fails post-deploy: `live: false`, restart gateway. No data destruction.
