---
title: "Escalation Policy — CAC Committee AI Agent System"
type: "concept"
department: "shared"
sources: ["PRD v2.2 Section 8 — Escalation Framework", "config/escalation_rules.json"]
related: ["data-governance", "breach-response", "covenant-monitoring"]
created: "2026-04-10"
updated: "2026-04-10"
confidence: "high"
coverage: "high"
tags: ["escalation", "governance", "notifications", "severity", "alert-policy"]
---

# Escalation Policy — CAC Committee AI Agent System

## Summary

Escalation is the mandatory process by which agents surface abnormal conditions — regulatory breaches, threshold violations, data conflicts, or unresponsive approvers — to the appropriate human decision-makers. Every agent must evaluate escalation triggers after each analysis. Escalation is never optional; suppressing an escalation is a Hard Rule violation.

## Definition

An escalation is a structured alert that:
1. Identifies the specific condition that triggered it
2. Classifies the severity (Critical / High / Medium / Low)
3. Routes notification to the correct party via the defined channel
4. Requires acknowledgement and documented resolution

Escalation thresholds are configured in `config/escalation_rules.json` and may be updated by the CAC committee without code changes.

## How It Works

**Severity Levels:**

| Severity | Meaning | Response SLA | Primary Channel |
|----------|---------|-------------|-----------------|
| Critical | Regulatory breach or imminent breach; legal/operational risk | Immediate (< 1 hour) | Email to HOD + Slack #cac-committee |
| High | Threshold violation; significant deterioration; no response to Critical | 24 hours | Slack #cac-committee + email if unacknowledged |
| Medium | Approaching threshold; trend deterioration; informational concern | 48 hours | Slack #cac-committee |
| Low | Informational; no action required but noted for record | Next scheduled review | Slack #cac-committee (weekly digest) |

**Notification chain by severity:**

Critical:
1. HOD of the relevant department — email with direct approval-ui link + Slack DM
2. If no acknowledgement within 1 hour — escalate to Deputy CEO / CFO
3. If no acknowledgement within 4 hours — escalate to Board Risk Committee (via email)

High:
1. CAC committee members — Slack #cac-committee message with details
2. If no acknowledgement within 24 hours — email to HOD

Medium:
1. CAC committee Slack channel message
2. Included in next scheduled committee report

Low:
1. Logged to agent output; included in weekly digest

**Escalation triggers by domain:**

Liquidity:
- LCR < 100% → Critical
- NSFR < 100% → Critical
- LCR < 110% → Medium
- Cash position decline > 20% MoM → High
- Current ratio < 1.00 → High

Capital:
- CAR < 12.5% → Critical
- CET1 < 7.0% → Critical
- RWA QoQ increase > 15% → High
- Leverage ratio < 3.5% → High

ALM / Interest Rate Risk:
- Duration gap > 3.0 years → Critical
- EVE sensitivity > 20% of equity → Critical
- NII sensitivity > 15% of net income → High

Funding / Covenants:
- Any covenant breach → Critical
- Covenant ratio within 10% of limit → Medium
- Facility utilisation > 90% → High
- Facility maturing < 30 days without renewal → Critical
- Cure period expiring < 7 days → High

Staging Pipeline:
- Approval pending > 48 hours → High
- No HOD response to Critical escalation > 1 hour → re-escalate to CFO

**Escalation format (agent output):**

```
ESCALATION: [SEVERITY] — [METRIC] — [TIMESTAMP]
Current value: [X] | Threshold: [Y] | Headroom: [margin]
Source: [document/Slack reference]
Recommended action: [specific action]
Assigned to: [role / Slack handle]
```

## Why It Matters

Regulatory ratio breaches carry legal consequences including mandatory regulator notification, distribution restrictions, and potential licence conditions. Early escalation gives management time to take corrective action. Delayed escalation — even by hours in a Critical scenario — may result in breach of regulatory notification deadlines (typically 24 hours from breach discovery).

## Key Metrics / Thresholds

| Metric | Threshold | Escalation |
|--------|-----------|------------|
| Critical acknowledgement | < 1 hour | Re-escalate to CFO if no response |
| High acknowledgement | < 24 hours | Email HOD if no Slack response |
| Escalation record completeness | 100% | Every escalation must be logged in ALCO Tracker audit trail |

## Related Concepts

- [[data-governance]] — Staging pipeline policy; approval escalation for pending proposals
- [[breach-response]] — Operational steps once a regulatory breach is confirmed
- [[covenant-monitoring]] — Covenant-specific escalation triggers

## Source References

- PRD v2.2, Section 8: Escalation Framework
- `config/escalation_rules.json` — machine-readable thresholds consumed by agents
- `config/hod_emails.json` — HOD routing table for email notifications
- `services/email-notifier/` — service that dispatches escalation emails

## Agent Notes

- Every agent must check its escalation triggers after completing an analysis — not only when updating the ALCO Tracker.
- An escalation must be raised even if the agent is not proposing a data change.
- Use `config/escalation_rules.json` as the authoritative threshold source — do not hardcode values.
- When multiple metrics breach simultaneously, raise all relevant escalations; do not merge them into a single alert.
- Log the escalation reference ID in the agent output so the committee can track resolution.
