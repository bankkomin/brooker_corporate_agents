---
title: "IC Knowledge Base"
type: index
department: "ic"
updated: "2026-05-06"
---

# IC Knowledge Base

Investment Committee knowledge base. Concepts, decisions, meeting notes, entities, and trends specific to the IC department.

## Agent Skills

These are the SKILL.md files that govern each IC agent's behaviour. They are mirrored from `skills/ic/` (runtime read path) into `obsidian-vault/skills/ic/` (wiki-visible) per the project convention. Edit the `skills/ic/` copies; the wiki copies are kept in sync at deployment.

- [[skills/ic/ic-chair-agent|IC Chair Agent]] — Committee chair, orchestrates all IC analysis (renamed from `ic-orchestrator` per Stage 16)
- [[skills/ic/portfolio|Portfolio]] — Portfolio review, ratio breaches, Red Flag tracking
- [[skills/ic/due-diligence|Due Diligence]] — DD pipeline, loan health, manager DD
- [[skills/ic/valuation|Valuation]] — MTM, FV hierarchy, DAT sell+call economics
- [[skills/ic/ic-orchestrator|ic-orchestrator]] *(deprecated stub)* — superseded by ic-chair-agent

## Sections

- **Concepts** — `ic/concepts/` — Foundational policy / domain knowledge
  - Policies: [[red-flag-policy]] · [[concentration-policy]] · [[investment-holding-limit]] · [[liquidity-management-policy]]
  - Doctrine / OKR: [[engine-framework]] · [[okr-500mb-recurring-income]]
- **Decisions** — `ic/decisions/` — Running committee decisions / objectives
  - Portfolio reduction: [[sukhothai-redemption]] · [[red-flag-portfolio-reduction]] · [[investment-holding-40pct-limit]]
  - Digital asset treasury: [[digital-asset-treasury-divestment]] · [[dat-sell-call-strategy]] · [[option-wheel-prediction-markets]] · [[prediction-market-pilot]]
  - Engines & doctrine: [[singapore-vcc-structure]] · [[bicl-movie-private-credit]] · [[capital-sovereignty-doctrine]]
  - Other: [[corporate-startup-partnerships]] · [[robinhood-token-ipo]] · [[nft-festival-cafe-capex]] · [[adfin-bot-waiver]]
  - **Proposals (draft, pre-vote):** [[q2-2026-rebalance-proposal]] *(2026-05-07 — BTC+BNB sell-down to 40%)* · companion HTML: `decisions/q2-2026-rebalance-proposal.html` *(mobile-friendly view)*
- **Meeting Notes** — `ic/meeting-notes/` — IC committee minutes
  - [[IC-2025-01-23]] · [[IC-2025-04-02]] · [[IC-2026-03-19]] *(deck-augmented from `IC No1 Mar 2026.pptx`)*
- **Entities** — `ic/entities/`
  - Listed: [[mill]] · [[pace]] · [[wave]] · [[wave-w3]] · [[b]] · [[b-w8]] · [[cv]]
  - Non-listed / Funds: [[sukhothai-fund]] · [[varuna]] · [[wavebcg]] · [[adfin]] · [[robinhood]] · [[bcgt]] · [[brooker]]
  - Digital / VC: [[binance-bnb-otc]] · [[nfts-cryptopunks-apes]] · [[exponential-digital-age-fund]] · [[brook-limited-partners-fof]]
  - Loan book: [[structured-loan-portfolio]] · [[chill-space-areeya]] · [[wave-expo]] · [[k-viwat-areeya-owner]] · [[purple-venture-robinhood]] · [[mr-phongphan]]
  - External partners: [[a16z-crypto-fund-v]] · [[pantera-fund]] · [[obsidian-creek-capital]] · [[hex-trust]] · [[fireblocks]] · [[deribit]]
- **Trends** — `ic/trends/` — Dashboards and historical analyses
  - [[dashboard-2026-02]] · [[portfolio-allocation-history]]
- **Templates** — `ic/templates/` *(ignored by vault watcher)*
  - `meeting-note.md` — canonical IC meeting-note **markdown** skeleton
  - `meeting-minutes-docx.md` — schema for generating the formal `.docx` minutes (per-section + per-table placeholder map)
  - `meeting-deck-pptx.md` — schema for generating the monthly `.pptx` deck (slide-by-slide content map)
- **Generation contract** — `config/templates/ic/`
  - `meeting-templates.json` — single source of truth: vault path → docx field → pptx slide mapping; output paths; approval workflow
  - `IC-meeting-minutes-reference.docx` — style / structure reference (sourced from Feb 2026 minutes)
  - `IC-meeting-deck-reference.pptx` — style / structure reference (sourced from Mar 2026 deck)
  - `IC-dashboard-reference.xlsx` — schema reference (Feb 2026 dashboard)

## Cross-department reads

Per Stage 16 spec, IC has cross-read access to: `finance` · `cio` · `vcc` · `legal`. (Recommend adding `cac` — IC liquidity / portfolio numbers overlap with CAC's ALCO Tracker.)

## Operations Log

- [[ic/log|Operations Log]]
