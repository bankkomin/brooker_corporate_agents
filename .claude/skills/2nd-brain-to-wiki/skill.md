---
name: 2nd-brain-to-wiki
description: Use when files in O:\2nd_Brain must become wiki knowledge, when external research reports / macro outlooks / regulatory documents need turning into timestamped Obsidian wiki articles, or when populating the macro / research / regulations knowledge areas. Covers extraction, timestamped source-summaries, recurring-thesis concepts, and entity articles.
---

## 2nd-brain-to-wiki Workflow

Converts external knowledge files (`O:\2nd_Brain\...`) into structured, **timestamped**
Obsidian wiki articles under the non-department knowledge areas `obsidian-vault/macro/`,
`obsidian-vault/research/`, and `obsidian-vault/regulations/`.

`$ARGUMENTS` = a `O:\2nd_Brain` subfolder name (e.g. `Crypto`, `Macro_and_Geopolitics`,
`Thai_SEC_regulations`).

**Data safety:** `O:\2nd_Brain` is external read-only material. All writes go to
`obsidian-vault/` and `.source-extracts/`.

### Folder → vault area mapping

| `O:\2nd_Brain` subfolder | Vault area |
|--------------------------|------------|
| `Macro_and_Geopolitics` | `macro` |
| `Crypto`, `AI_tech_innovation`, `Pitchbook`, `Brainstorm`, `Counterparties`, `Risk`, `Compliance`, `Contracts`, `Thailand` | `research` |
| `Thai_SEC_regulations` | `regulations` |

### Format authority

`config/wiki_schema.json` defines article types and frontmatter. `obsidian-vault/ic/` and
`obsidian-vault/ceo/` show house style. This content is **external and point-in-time** —
unlike department wikis, the primary article type is `source-summary`, not `decision_log`.

### 1. Extract source content

```
python scripts/extract_sources.py --root "O:/2nd_Brain" <Subfolder>
```
Output lands in `.source-extracts/2nd_brain/<Subfolder>/` (gitignored). Each extract
header records `_Modified: YYYY-MM-DD_` — the source file timestamp. Large PDFs are
streamed page-by-page; never Read a raw source file directly (32 MB limit). Saved-webpage
assets (`.js/.css/.gif/.db`) are skipped automatically.

### 2. Classify and author articles

Write into the mapped vault area's `concepts/`, `entities/`, `trends/` subfolders.

| Type | Directory | Filename | When |
|------|-----------|----------|------|
| `source-summary` | `concepts/` | `source-{slug}.md` | One per substantive report/document |
| `concept` | `concepts/` | `{slug}.md` | A recurring thesis several sources touch |
| `entity` | `entities/` | `{slug}.md` | Research houses, funds, protocols, firms, regulators |
| `trend` | `trends/` | `{slug}.md` | Time-series / dated market or regulatory data |

- One `source-summary` per report — sections: Document Overview, Key Findings, Relevance,
  Extracted Data. Lead with the **as-of date**.
- Promote major recurring theses into their own `concept` articles, cross-linked from the
  source-summaries that discuss them.
- Saved-webpage bundles and `.msg` emails: summarise the substantive document; ignore the
  asset clutter.

### 3. Timestamps (required)

Every article's frontmatter MUST carry:
- `source_date` — the source file's modified date (from the extract `_Modified:` header)
  or a more precise date found in the document.
- `period` — the period the content concerns (e.g. `"2023"`, `"2026-Q2"`, `"Jun 2022"`).

For `regulations`, also record `effective_date` where stated, and note supersedence when
a later rule replaces an earlier one (folder names carry years: 2022 → 2026).

### 4. Frontmatter

```yaml
---
title: "Human Readable Title"
type: "source-summary"        # source-summary | concept | entity | trend
department: "research"        # macro | research | regulations
sources: ["Original File.pdf"]
source_date: "2023-01-15"
period: "2023"
related: ["other-slug"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"
coverage: "medium"
tags: ["research", "crypto", "thesis"]
---
```

### 5. Index, log, self-check, commit

- Update the area `index.md` — link new articles grouped by section.
- Append the area `log.md`: `## [YYYY-MM-DD] ingest | <N> articles from 2nd_Brain/<Subfolder>`.
- Verify every `[[link]]` resolves to a real file in `obsidian-vault/`.
- Commit per subfolder/batch: `feat(wiki): <area> knowledge from 2nd_Brain/<Subfolder>`.

### Common mistakes

- Reading a raw source file directly instead of the extract — large files exceed limits.
- Omitting `source_date` / `period` — these articles are point-in-time and recalled by date.
- Authoring department-style `decision_log` articles — external research uses `source-summary`.
- Treating saved-webpage `.js/.css/.gif` clutter as content.
