---
name: skill-writer
description: Write SKILL.md files per the PRD Section 11 format standard. Use when creating agent skill definitions for the CAC orchestrator's domain-specific agents (liquidity, capital, ALM, funding, escalation, CFO).
---

## SKILL.md Writing Workflow

### 1. Read Context
- Read `PRD.md` Section 11 for the SKILL.md format standard
- Read `config/excel_schema/alco_tracker.json` for Excel structure (if it exists)
- Read `config/escalation_rules.json` for escalation triggers (if it exists)
- Read existing skills in `skills/` for consistency

### 2. Follow the Standard Format
Every SKILL.md must have ALL of these sections:

```markdown
---
name: [skill-name]
agent: [agent-name]
dept: cac
version: 1.0
---

## Mandate
[What this agent owns. What it does NOT own. Be explicit about boundaries.]

## Tone & Style
[Formal. Cite sources. Never speculate. Max response length. Format requirements.]

## Domain Knowledge
[Key terms, thresholds, ratios, policy references. QUANTITATIVE and SPECIFIC.
Never vague — "ratio > 3.2x" not "ratio is high".]

## Retrieval Instructions
[Which Chroma collections to search. Metadata filters. Min relevance: 0.70. Top-K: 8.]

## Staging Proposal Rules
[When to propose a cell change. Minimum confidence: 0.85. What evidence is required.
What must be in the manifest. When NOT to propose.]

## Excel Navigation
[Which tabs, rows, columns this agent navigates.
Navigation format: "ALCO Tracker → Tab: {tab} → Row {n}: {label} → Column {col}"]

## Escalation Triggers
[Quantitative triggers ONLY. Example:
- SCB covenant ratio within 10% of 3.5x threshold
- Liquidity buffer below 500M THB
- Capital request exceeds 200M THB delegation limit]

## Output Format
[Required sections in every response. Citation format. Confidence indicator.]

## Hard Rules
[What this agent must NEVER do. E.g.:
- Never speculate beyond retrieved evidence
- Never propose changes with confidence < 0.85
- Never write directly to corporate files]
```

### 3. Build Priority (from PRD)
1. `skills/shared/escalation-protocol.md`
2. `skills/shared/citation-format.md`
3. `skills/cac/cfo-agent.md` ← start here for CAC
4. `skills/cac/covenant-monitoring.md`
5. `skills/cac/liquidity-analysis.md`
6. `skills/cac/capital-allocation.md`
7. `skills/cac/alm-review.md`
8. `skills/cac/funding-facilities.md`
9. `skills/shared/excel-navigation.md`
10. `skills/shared/rag-retrieval.md`

### 4. Cross-Reference
- Skills in `skills/cac/` should reference each other where relevant
- CFO Agent skill should reference all other CAC skills
- Use Obsidian-compatible `[[links]]` between skills for knowledge graph navigation
