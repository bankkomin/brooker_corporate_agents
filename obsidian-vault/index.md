---
title: Brooker Corporate Agent Knowledge Vault
type: index
updated: 2026-05-26
---

# Brooker Corporate Agent — Knowledge Vault

Welcome to the corporate knowledge base. This vault is the human-readable source of truth for agent skills, department knowledge, meeting notes, and decision logs. The VaultWatcher ingests every change into Qdrant within ~60 seconds so agents can cite vault content in their responses.

## Department Knowledge Bases

### Committee & decision-making
- [[ceo/index|CEO]] — Strategy, board resolutions, governance, corporate worldview
- [[cac/index|CAC]] — Capital Allocation & ALCO Committee
- [[ic/index|IC]] — Investment Committee (portfolio, DD, valuation)
- [[cio/index|CIO]] — Chief Investment Officer / Head of Investment

### Functional departments
- [[finance/index|Finance]] — BICL, audited financials, intercompany loans
- [[legal/index|Legal]] — Compliance, regulatory affairs, contract review
- [[hr/index|HR]] — Human resources policies and decisions
- [[comms/index|Communications]] — Brand and external comms
- [[vcc/index|VCC]] — Venture capital and crypto fund knowledge

### Cross-cutting knowledge areas
- [[shared/index|Shared]] — Cross-department policies and protocols
- [[research/index|Research]] — External theses, crypto/AI/macro research (point-in-time, sourced from `O:\2nd_Brain`)
- [[regulations/index|Regulations]] — Thai SEC rules, corporate governance, compliance concepts
- [[macro/index|Macro]] — Macroeconomic trends and asset-class analysis

### Phase 2 scaffolds *(per-dept rollout, Stages 11–19)*
- [[ib/index|IB]] — Investment Banking *(planned)*
- [[invest/index|Investment]] — Investment Committee operations *(planned)*
- [[it/index|IT]] — Information Technology *(planned)*
- [[ops/index|Operations]] — Operations and facilities *(planned)*
- [[risk/index|Risk]] — Risk Committee *(planned)*

## Agent Skills

### Shared skills
- [[skills/shared/rag-retrieval|RAG Retrieval]] — How agents search documents and chat history
- [[skills/shared/excel-navigation|Excel Navigation]] — How agents find cells in ALCO Tracker
- [[skills/shared/escalation-protocol|Escalation Protocol]] — Breach detection and notification tiers
- [[skills/shared/citation-format|Citation Format]] — Source attribution standards
- [[skills/shared/wiki-maintenance|Wiki Maintenance]] — Per-dept lint, archive, gap reports
- [[skills/shared/vault-health-check|Vault Health Check]] — Vault-wide rollup + cross-dept checks
- [[skills/shared/paperclip-service|Paperclip Service]] — Agent orchestration shell integration

### CAC Committee skills
- [[skills/shared/cfo-agent|CFO Agent]] — Committee chair, orchestrates all CAC analysis *(deprecation stub — canonical path `skills/finance/cfo-agent` lands with Phase 2 finance stage)*
- [[skills/cac/liquidity-analysis|Liquidity Analysis]] — LCR, NSFR, cash position monitoring
- [[skills/cac/capital-allocation|Capital Allocation]] — RWA, CAR, dividend policy
- [[skills/cac/covenant-monitoring|Covenant Monitoring]] — Debt covenant compliance tracking
- [[skills/cac/alm-review|ALM Review]] — Duration gap, rate sensitivity analysis
- [[skills/cac/funding-facilities|Funding Facilities]] — Credit facilities, debt management

### Investment Committee skills
- [[skills/ic/ic-chair-agent|IC Chair Agent]] — Committee chair, IC synthesis
- [[skills/ic/portfolio|Portfolio]] — Portfolio review, ratio breaches, Red Flag tracking
- [[skills/ic/due-diligence|Due Diligence]] — DD pipeline, loan health, manager DD
- [[skills/ic/valuation|Valuation]] — MTM, FV hierarchy, DAT sell+call economics

### Per-dept skills *(planned — Phase 2)*
- `skills/hr/`, `skills/invest/`, `skills/risk/`, `skills/ops/`, `skills/it/`

## Templates
- [[templates/concept|Concept Article]] — Domain knowledge article template
- [[templates/decision|Decision Log]] — Committee decision record template
- [[templates/meeting-note|Meeting Note]] — ALCO / department meeting template
- [[templates/entity|Entity]] — Counterparty, facility, or instrument profile template
- [[templates/escalation|Escalation Protocol]] — Escalation procedure template

## Shared Resources
- [[shared/policies/|Policies]] — Shared policy documents (auto-ingested within 60 seconds)
- [[shared/escalation-protocols/|Escalation Protocols]] — Shared escalation procedures

## Operations
- [[log|Vault Operations Log]] — Rolling timeline of vault-wide events (health checks, ingestion summaries, structural changes)

---

> **How this works:** When you save a file in this vault, the VaultWatcher automatically ingests it into the Qdrant knowledge collections. Agents can then cite vault content in their responses. Changes are picked up within 60 seconds (with a 5-second debounce to avoid partial saves).
