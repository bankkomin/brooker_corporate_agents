---
title: "Data Governance Policy — AI Agent Staging Pipeline"
type: "concept"
department: "shared"
sources: ["PRD v2.2 Section 3 — Data Safety Rule", "PRD v2.2 Section 5 — Data Zones"]
related: ["escalation-policy", "breach-response"]
created: "2026-04-10"
updated: "2026-04-10"
confidence: "high"
coverage: "high"
tags: ["governance", "data-safety", "staging", "approval", "pipeline"]
---

# Data Governance Policy — AI Agent Staging Pipeline

## Summary

No AI agent may write directly to corporate data. All proposed changes flow through a mandatory staging pipeline with a human approval gate before any data is modified in the live system. This policy applies to every agent in the Corporate AI Agent System without exception. Violation constitutes a critical system failure.

## Definition

The staging pipeline is a four-zone architecture that enforces separation between agent-proposed changes and live corporate data:

| Zone | Location | Access |
|------|----------|--------|
| Zone 0 | Corporate data (source of truth) | External — never agent-accessible |
| Zone 1 | `/data/mirror/` | Read-only mount for all agent containers |
| Zone 2 | `/data/staging/` (pending / approved / rejected) | Agents write ONLY to `pending/`; read all |
| Zone 3 | Approval Gate (approval-ui, port 4000) | Human-only review and decision |
| Zone 4 | `/data/archive/` | Permanent audit log; sync-back to corporate |

## How It Works

**Ingestion (Zone 0 → Zone 1):**

The `sync-mirror` service pulls data from corporate systems to `/data/mirror/` every 15 minutes. This is a pull-only, read-only operation. No agent has write access to Zone 1. Docker enforces the `:ro` (read-only) mount flag on all agent containers.

**Staging (Zone 1 → Zone 2):**

When an agent identifies a value that should be updated in the ALCO Tracker (or any tracked document), it creates a staging manifest and writes it to `/data/staging/pending/` via `staging_writer.py`. The manifest must conform to the Staging Proposal Manifest Schema:

```json
{
  "id": "chg_XXXX",
  "agent": "funding-agent",
  "file": "ALCO_Tracker.xlsx",
  "tab": "Funding Facilities",
  "cell": "E8",
  "old_value": null,
  "new_value": "3.15",
  "source": "Slack #cac-committee | Jane Doe | 2026-03-24T10:42",
  "confidence": 0.91,
  "reasoning": "...",
  "status": "pending"
}
```

All proposals require:
- Minimum confidence score of 0.85
- At least one source citation with document name, page, or Slack message reference
- `old_value` populated from the current mirror value (not assumed)

**Approval Gate (Zone 2 → Zone 3):**

The `email-notifier` service sends the relevant Head of Department (HOD) an email with a direct link to the approval-ui (port 4000). The HOD reviews:
- The proposed change (old value vs. new value, cell reference, tab)
- The source evidence and agent reasoning
- The confidence score

The HOD selects Approve or Reject. Approved changes move to `/data/staging/approved/` and trigger `sync-back`. Rejected changes move to `/data/staging/rejected/` for audit.

**Sync Back (Zone 3 → Zone 4 → Zone 0):**

The `sync-back` service reads from `/data/staging/approved/` and applies the change to the corporate system. The applied change is then archived to `/data/archive/` with a full audit trail (timestamp, approver, agent, source evidence).

## Why It Matters

The staging pipeline prevents:
1. **Erroneous data corruption** — agent hallucinations or low-confidence extractions cannot modify live data.
2. **Untracked changes** — every modification has a full provenance record.
3. **Unauthorised access** — Docker `:ro` mounts make Zone 1 physically unwritable by agents.
4. **Audit failure** — Zone 4 archive satisfies regulatory record-keeping requirements.

## Key Metrics / Thresholds

| Metric | Threshold | Escalation |
|--------|-----------|------------|
| Proposal confidence | ≥ 0.85 required to submit | Block proposal if below |
| Source citation | Mandatory for every proposal | Block proposal if missing |
| Approval response time | HOD must respond within 24h | Escalate to backup approver if no response |
| Pending queue age | Alert if any proposal > 48h in pending | High escalation |

## Related Concepts

- [[escalation-policy]] — Defines what triggers notifications and who is contacted
- [[breach-response]] — Steps when a regulatory ratio breach is detected

## Source References

- PRD v2.2, Section 3: Data Safety Rule
- PRD v2.2, Section 5: Data Zone Architecture
- `staging_writer.py` — the only authorised write path to `/data/staging/pending/`
- `config/hod_emails.json` — maps departments to HOD email addresses

## Agent Notes

- Agents NEVER call any file write operation on `/data/mirror/` — always use `staging_writer.py`.
- A proposal with confidence < 0.85 must NOT be submitted; the agent should report uncertainty to the committee instead.
- If multiple conflicting sources exist for the same value, the agent must NOT submit a proposal — report the discrepancy with citations.
- The `old_value` field in the manifest must reflect the value currently in the mirror, retrieved at the time of proposal.
- Agents may read from `/data/staging/pending/` and `/data/staging/approved/` to avoid proposing duplicate changes.
