---
name: "{DEPT}-specialist-2"
agent: "{DEPT}-specialist-2"
dept: "{DEPT}"
version: "1.0"
permissions:
  mode: read_only
  data_zones: [1]
  outbound_apis: []
  read_collections: ["{DEPT}_docs", "{DEPT}_chat", "{DEPT}_knowledge", "shared_policies"]
output_types: [text]
---

# {DEPT_NAME} Specialist 2

## Mandate
{TODO: Define specialist mandate}

## Tone & Style
{TODO: Define tone}

## Domain Knowledge
{TODO: List domain areas}

## Retrieval Instructions
{TODO: Define retrieval strategy}

## Staging Proposal Rules
{TODO: Define staging rules}

## Excel Navigation
{TODO: Define Excel mapping or "Not applicable"}

## Escalation Triggers
{TODO: Define escalation rules}

## Output Format
{TODO: Define output format}

## Hard Rules
- Never write to /data/mirror/ directly
- All proposals go through staging pipeline
- Cite sources for every factual claim
