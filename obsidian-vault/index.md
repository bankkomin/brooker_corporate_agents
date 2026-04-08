---
title: Brooker Corporate Agent Knowledge Vault
type: index
updated: 2026-04-07
---

# Brooker Corporate Agent — Knowledge Vault

Welcome to the corporate knowledge base. This vault is the human-readable source of truth for agent skills, department knowledge, meeting notes, and decision logs.

## Department Indexes

- [[cac/index|CAC Knowledge Base]] — Capital Allocation & ALCO Committee
- [[hr/index|HR Knowledge Base]] — Human Resources
- [[shared/index|Shared Knowledge Base]] — Cross-department policies and protocols

## Agent Skills

### Shared Skills

- [[skills/shared/rag-retrieval|RAG Retrieval]] — How agents search documents and chat history
- [[skills/shared/excel-navigation|Excel Navigation]] — How agents find cells in ALCO Tracker
- [[skills/shared/escalation-protocol|Escalation Protocol]] — Breach detection and notification tiers
- [[skills/shared/chat-ingestion|Chat Ingestion]] — How Slack messages become searchable
- [[skills/shared/citation-format|Citation Format]] — Source attribution standards

### CAC Committee Skills

- [[skills/cac/cfo-agent|CFO Agent]] — Committee chair, orchestrates all CAC analysis
- [[skills/cac/liquidity-analysis|Liquidity Analysis]] — LCR, NSFR, cash position monitoring
- [[skills/cac/capital-allocation|Capital Allocation]] — RWA, CAR, dividend policy
- [[skills/cac/covenant-monitoring|Covenant Monitoring]] — Debt covenant compliance tracking
- [[skills/cac/alm-review|ALM Review]] — Duration gap, rate sensitivity analysis
- [[skills/cac/funding-facilities|Funding Facilities]] — Credit facilities, debt management

### HR Skills

- [[skills/hr/|HR Skills]] — HR department agent skills

## Templates

- [[templates/concept|Concept Article]] — Domain knowledge article template
- [[templates/decision|Decision Log]] — Committee decision record template
- [[templates/meeting-note|Meeting Note]] — ALCO / department meeting template
- [[templates/entity|Entity]] — Counterparty, facility, or instrument profile template
- [[templates/escalation|Escalation Protocol]] — Escalation procedure template

## Shared Resources

- [[shared/policies/|Policies]] — Shared policy documents (auto-ingested within 60 seconds)
- [[shared/escalation-protocols/|Escalation Protocols]] — Shared escalation procedures

---

> **How this works:** When you save a file in this vault, the VaultWatcher automatically ingests it into the Qdrant knowledge collections. Agents can then cite vault content in their responses. Changes are picked up within 60 seconds (with a 5-second debounce to avoid partial saves).
