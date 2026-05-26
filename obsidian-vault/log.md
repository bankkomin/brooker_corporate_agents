---
title: Vault Operations Log
type: log
scope: vault
updated: 2026-05-26
---

# Vault Operations Log

Rolling timeline of vault-wide operations. Per-department logs live at `{dept}/log.md`; this file captures cross-vault events that don't belong to any single department.

## Conventions

Entry format (per `[[skills/shared/wiki-maintenance]]`):

```
## [YYYY-MM-DD] operation | one-line description
Optional second line with affected paths or counts.
```

**Operation tags used here:**
- `health-check` — vault-wide scan output summary (full report lives in `health-reports/`)
- `structure` — structural changes to the vault (new dept, removed dept, root index revision)
- `ingestion` — large or notable ingestion events (bulk import, schema change)
- `migration` — when content moves between depts or paths

Writers: `[[skills/shared/vault-health-check]]` appends `health-check` entries. Humans append `structure` / `migration` entries during refactors. Ingestion service may append `ingestion` entries for bulk operations.

## Entries

## [2026-05-26] structure | Root `index.md` expanded to catalog all 17 dept + shared knowledge bases; `log.md` introduced.
Previously root index listed only cac, hr, shared. New entry surfaces all live depts (ceo, cac, ic, cio, finance, legal, hr, comms, vcc), cross-cutting knowledge areas (shared, research, regulations, macro), and Phase 2 scaffolds (ib, invest, it, ops, risk).

## [2026-05-26] structure | `[[skills/shared/vault-health-check]]` skill spec added.
Complements per-dept `[[skills/shared/wiki-maintenance]]` with vault-wide rollup + cross-dept checks (broken skill links, duplicate entity names across depts, inter-dept wikilink resolution).

## [2026-05-26] health-check | 0 critical, 9 warning, 5 info across 18 depts. Report: health-reports/2026-05-26.md
