---
name: rag-retrieval
agent: all
dept: shared
version: 1.0
---

## Mandate
Guide agents on how to interpret and use retrieved context from the Qdrant vector store. Defines relevance thresholds, multi-source synthesis rules, and context quality assessment.

## Tone & Style
- Treat retrieved context as evidence, not as absolute truth
- Always assess relevance and recency before incorporating
- Explicitly note when retrieved context is stale or contradictory

## Domain Knowledge
Qdrant collections:
- **cac_docs:** Uploaded documents (Excel trackers, PDFs, reports)
- **cac_chat:** Indexed Slack messages from committee channels
- **cac_knowledge:** Obsidian vault knowledge base entries
- **shared_policies:** Cross-department policy documents

Relevance scoring:
- **0.90+:** High confidence — use as primary evidence
- **0.80-0.89:** Good — use with light verification
- **0.70-0.79:** Marginal — use only if no better sources
- **Below 0.70:** Filtered out by retrieval pipeline

## Retrieval Instructions
- Top-8 results returned per query (configurable)
- Minimum relevance threshold: 0.70
- Prioritize cac_docs over cac_chat for financial data
- Prioritize cac_chat over cac_docs for recent discussions and decisions
- Synthesize across collections — do not rely on a single collection

## Staging Proposal Rules
- Proposals require at least one source with relevance >= 0.80
- Source excerpt must be included verbatim (first 200 chars)
- If only marginal sources available, do not propose — provide analysis only

## Excel Navigation
Not applicable — retrieval is cross-cutting.

## Escalation Triggers
Not applicable — retrieval does not trigger escalation.

## Output Format
When citing retrieved context:
- Include relevance score in internal reasoning (not in user-facing response)
- User-facing: use citation format from citation-format.md
- Internal: log source quality metrics for audit

## Hard Rules
- NEVER use context below 0.70 relevance
- NEVER present a single low-relevance source as definitive
- ALWAYS disclose when context may be outdated (check date metadata)
- If no relevant context found, say "I don't have sufficient information" — never hallucinate
