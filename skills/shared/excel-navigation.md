---
name: excel-navigation
agent: all
dept: shared
version: 1.0
---

## Mandate
Define how agents map proposed values to specific cells in the ALCO Tracker Excel workbook. All cell references must be validated against the alco_tracker.json schema.

## Tone & Style
- Cell references use A1 notation: "E8", "D12", "B3"
- Tab names match Excel exactly (case-sensitive): "Liquidity", "Capital", "ALM", "Funding Facilities"
- Always include tab + cell in proposals

## Domain Knowledge
ALCO Tracker structure (from alco_tracker.json):
- **Liquidity tab:** Current ratio (D8), Quick ratio (D9), LCR (D10), NSFR (D11), Cash position (D12)
- **Capital tab:** CAR (D8), CET1 (D9), Tier 1 (D10), RWA (D11), Leverage ratio (D12)
- **ALM tab:** Duration gap (D8), NII sensitivity (D9), EVE sensitivity (D10), Repricing gap (D11)
- **Funding Facilities tab:** Total drawn (D8), Total available (D9), Utilization % (D10), Covenant ratio (E8)

Note: These are indicative mappings. Always verify against alco_tracker.json for current cell positions.

## Retrieval Instructions
- Load alco_tracker.json schema at agent startup
- Map proposed values to cells using the schema's row/column definitions
- If the target cell cannot be identified, do not propose — provide analysis only

## Staging Proposal Rules
- Every proposal MUST include: file, tab, cell, old_value (if known), new_value
- Cell references must exist in alco_tracker.json
- If schema doesn't cover the target metric, flag as "unmapped" and do not propose

## Excel Navigation
This IS the excel navigation skill — defines the master rules for all agents.

## Escalation Triggers
Not applicable — navigation itself does not trigger escalation.

## Output Format
When proposing changes, include in reasoning:
"Mapped to: ALCO_Tracker.xlsx -> [Tab Name] -> Cell [XX] (column: [description], row: [description])"

## Hard Rules
- NEVER propose a cell update without validating against alco_tracker.json
- NEVER guess cell references — if unsure, provide analysis only
- ALWAYS include the tab name with every cell reference
- old_value should be populated from the most recent known value (from retrieval)
