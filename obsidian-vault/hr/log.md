---
title: "HR Operations Log"
type: log
department: "hr"
---

## [2026-04-07] init | Wiki knowledge base initialized for hr department

## [2026-05-17] ingest | 5 articles from brooker_database/hr

One-shot ingest of both source files in `O:\brooker_database\hr` via the
`brooker-db-to-wiki` skill. Both sources are Thai-language internal-control
self-assessment questionnaires (แบบสอบถามการควบคุมภายใน); articles authored in English
with key Thai terms preserved.

Sources:
- `แบบสอบถาม การเก็บเอกสารสัญญาจ้าง.pdf` → [[employment-contract-document-retention]],
  [[internal-control-questionnaire-employment-contract-storage]]
- `แบบสอบถาม การให้สิทธิพนักงานทำงานที่บ้าน (WFH).pdf` → [[work-from-home-policy]],
  [[internal-control-questionnaire-wfh-rights]]
- Both → [[internal-control-self-assessment-questionnaire]] (shared instrument concept)

Articles: 3 concepts, 2 entities.

Note: the PDFs are scanned single-page forms — `scripts/extract_sources.py` produced empty
markdown; content was read directly from the source PDFs. Both questionnaires only record
self-assessed control statuses, so no `decision_log` was created — no finalized policy
text or board decision is present in the sources.
