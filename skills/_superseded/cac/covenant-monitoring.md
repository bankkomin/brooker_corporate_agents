---
name: covenant-monitoring
agent: all
dept: cac
version: 1.0
permissions:
  mode: write_via_staging
  data_zones: [1, 2]
  outbound_apis: []
  read_collections: [cac_docs, cac_chat, cac_knowledge, shared_policies, finance_docs, risk_docs, cio_docs, ceo_docs]
output_types: [text, table, checklist]
---

## Mandate
Cross-agent skill for covenant breach detection and monitoring. All specialist agents must check covenant compliance when their analysis touches covenant-relevant metrics.

## Tone & Style
- Use precise legal/financial language: "breach", "cure period", "waiver", "notification"
- Always state both the covenant limit and the current value
- Never downplay covenant breaches — they have legal consequences

## Domain Knowledge
Common covenants:
- **Leverage ratio:** Net Debt / EBITDA (typical: < 4.0x)
- **Interest coverage:** EBITDA / Interest Expense (typical: > 3.0x)
- **Current ratio:** Current Assets / Current Liabilities (typical: > 1.20x)
- **Minimum net worth:** Total equity floor (varies by facility)
- **Capital expenditure cap:** Annual capex limit

Cure mechanisms:
- Cure periods: typically 30-60 days from breach detection
- Equity cure: injection of equity to restore compliance
- Waiver: lender agreement to temporarily ignore breach

## Retrieval Instructions
- Check escalation_rules.json for current covenant thresholds
- Search cac_docs for facility agreements containing covenant schedules
- Search cac_chat for any recent waiver discussions or cure actions

## Staging Proposal Rules
- Covenant status itself is NOT proposed to Excel
- Metrics that affect covenant compliance ARE proposed via their respective agents
- If a proposed change would cause a covenant breach, BLOCK the proposal

## Excel Navigation
Not applicable — covenant monitoring is cross-cutting. Individual metrics are managed by their respective agents.

## Escalation Triggers
- Any covenant breach -> Critical (immediate)
- Within 10% of any covenant limit -> Medium (approaching threshold)
- Cure period expiring within 7 days -> High (24h)

## Output Format
When covenant issue detected:
```
COVENANT ALERT: [covenant type]
Current: [value] | Limit: [threshold] | Headroom: [margin]
Status: [compliant/approaching/breached]
Cure period: [if applicable]
```

## Hard Rules
- NEVER suppress a covenant breach detection
- ALWAYS check all relevant covenants when updating financial metrics
- NEVER assume a waiver exists unless explicitly found in retrieved context
- If multiple covenants are affected, report ALL of them
