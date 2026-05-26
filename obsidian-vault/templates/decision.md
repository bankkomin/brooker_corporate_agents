---
date: "{{date}}"
type: decision
committee: CAC
decision-id: "CAC-{{date}}-001"
status: active
event_date: ""
tags: [decision, cac]
---

# Decision: {{title}}

## TL;DR for Agents

**Retrieved by:** [[skills/<dept>/<skill-name>]]
**Answers:** "One-line question this decision resolves."
**Key facts:** 1-2 sentences naming the decision outcome, any threshold or cap, and the binding constraint that drove it.

## Context
What situation or question prompted this decision.

## Options Considered
1. **Option A** — Description and trade-offs
2. **Option B** — Description and trade-offs

## Decision
The specific decision made. Quantitative where relevant (e.g., "threshold set at 3.5×").

## Rationale
Why this decision was made. Links to supporting [[skills/]] or [[policies/]].

## Impact
- **Affected systems:**
- **Affected departments:**
- **Timeline:**

## Approved By
- Name · Role · Date

## Related Skills
- [[skills/cac/liquidity-analysis]]
- [[skills/cac/covenant-monitoring]]

## Review Date
{{review_date}}

---

## Conventions (reference, delete when filling in)

**Bi-temporal `event_date`** *(optional)* — frontmatter `date` is when the committee decided. Set `event_date: YYYY-MM-DD` when the underlying business event has its own date that matters for audit: loan signing, instrument issuance, breach occurrence, contract execution. Leave blank when the decision date is the only relevant date.

**TL;DR for Agents** *(required)* — 3-line machine-readable preamble. See `templates/concept.md` for the full format spec. For decisions, "Key facts" should always include the decision outcome and any quantitative threshold or cap.
