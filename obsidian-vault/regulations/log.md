---
title: "Regulations Operations Log"
type: log
department: "regulations"
---

## [2026-05-17] init | Regulations knowledge area created (folder skeleton)

External regulatory reference area created for ingest from
`O:\2nd_Brain\Thai_SEC_regulations`.

## [2026-05-17] ingest | 135 articles from 2nd_Brain/Thai_SEC_regulations

Ingested the Thai SEC / SET regulatory archive (~906 source files; 749 substantive
extracts after excluding saved-webpage assets) via the `2nd-brain-to-wiki` skill, across
10 parallel authoring batches covering ~101 regulation-topic folders.

- 93 `concept` articles — one per regulation topic (listing, offerings, debt, MT/RPT,
  governance, digital assets, funds, accounting standards, tax, statutes).
- 35 `source-summary` articles for substantively distinct primary documents.
- 6 `entity` articles — regulators and referenced bodies/instruments.
- 1 `trend` article (SRI fund approvals 2022-2024).
- All articles carry `source_date`; regulation articles carry `effective_date` where stated.

Known follow-ups: a handful of near-duplicate concepts emerged from parallel batching
(TFRS 2, TFRS 16, SEA, MT/RPT 2026) — listed in `index.md` for a future consolidation
pass. Many source PDFs were image-only Thai scans — affected articles flagged
low-confidence pending OCR re-extraction.
