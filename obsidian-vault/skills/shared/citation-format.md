---
name: citation-format
agent: all
dept: shared
version: 1.0
---

## Mandate
Define the standard citation format for all agent responses. Every factual claim must be traceable to a specific source document or message.

## Tone & Style
- Citations are inline, enclosed in square brackets
- Format: [Source: filename, page X] or [Source: Slack #channel | Author | date]
- Multiple sources separated by semicolons

## Domain Knowledge
Source types:
- **Documents:** [Source: ALCO_Tracker.xlsx, Liquidity tab]
- **Chat messages:** [Source: Slack #cac-committee | Jane Doe | 2026-03-24]
- **Knowledge base:** [Source: KB: liquidity-policy-2026.md]
- **Multiple:** [Sources: ALCO_Tracker.xlsx, Liquidity tab; Slack #cac-committee | CEO]

## Retrieval Instructions
- Every claim must map to at least one retrieved source
- If no source supports a claim, prefix with "Based on general financial principles: "
- Never fabricate or hallucinate source references

## Staging Proposal Rules
- Every staging proposal MUST include a source citation in the reasoning field
- The source_excerpt field must contain the actual text from the source
- Proposals without citations are automatically blocked

## Excel Navigation
Not applicable — citation format is cross-cutting.

## Escalation Triggers
Not applicable — citation format does not trigger escalation.

## Output Format
Inline citations: "The current LCR stands at 125% [Source: ALCO_Tracker.xlsx, Liquidity tab], which exceeds the regulatory minimum of 100%."

## Hard Rules
- NEVER present information without a citation
- NEVER fabricate source references
- ALWAYS use the exact filename from the retrieved sources
- If confidence in source mapping is below 0.70, state "Source uncertain" explicitly
