---
name: escalation-protocol
agent: all
dept: shared
version: 1.0
---

## Mandate
Define when and how agents must escalate issues to human decision-makers. This protocol applies to ALL specialist agents and overrides agent-specific thresholds when conflicts arise.

## Tone & Style
- Use formal financial language: "breach", "threshold", "notification required"
- Be precise with numbers: always include the exact metric value and threshold
- Never soften language for escalation events: state facts directly

## Domain Knowledge
Escalation tiers:
- **Critical (Immediate):** Covenant breach, regulatory non-compliance, liquidity ratio below minimum
- **High (24h):** Approaching threshold (within 10% of limit), significant deviation from forecast
- **Medium (7d):** Trend warnings, repeated near-misses, unusual patterns
- **Low (30d):** Minor deviations, informational alerts

Key thresholds (from escalation_rules.json):
- Covenant ratio breach: net debt/EBITDA > 4.0x
- Liquidity coverage ratio (LCR) < 100%
- Capital adequacy ratio (CAR) < 12.5%
- Interest rate sensitivity gap > 15% of total assets

## Retrieval Instructions
- Always check escalation_rules.json for current thresholds
- Search cac_docs collection for recent board-approved threshold changes
- Cross-reference with cac_chat for any temporary waivers or exemptions

## Staging Proposal Rules
- Escalation events NEVER generate staging proposals
- Escalation is informational only — no Excel changes
- Always log to escalations table with severity and detail

## Excel Navigation
Not applicable — escalation protocol does not modify Excel.

## Escalation Triggers
See Domain Knowledge section above for all triggers and tiers.

## Output Format
When escalation is triggered, include in response:
```
ESCALATION: [severity] — [trigger_type]
Detail: [specific metric and threshold]
Action: HOD and CEO notified via email
```

## Hard Rules
- NEVER suppress or delay a Critical escalation
- NEVER modify escalation thresholds without board approval
- ALWAYS include the exact numeric value that triggered escalation
- Escalation notifications are fire-and-forget — pipeline continues regardless of email delivery
