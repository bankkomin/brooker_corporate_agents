---
name: brooker-db-to-wiki
description: Use when raw corporate files in O:\brooker_database must become wiki knowledge, when new source documents need turning into Obsidian vault articles, or when populating a department's knowledge base from source files. Covers docx/pdf/xlsx/pptx extraction, decomposition into concept/decision/entity/meeting-note articles, and document_inventory.json registration.
---

## brooker-db-to-wiki Workflow

Converts raw corporate source files (`O:\brooker_database\{dept}\...`) into structured
Obsidian wiki articles under `obsidian-vault/{dept}/`, then registers each source in
`config/document_inventory.json`.

`$ARGUMENTS` = a department name (`ceo`, `cio`, `comms`, `finance`, `hr`, `ic`, `legal`,
`vcc`) or `all`.

**Data safety:** `O:\brooker_database` is external corporate data — READ ONLY. Never write
to it. All writes go to `obsidian-vault/`, `config/`, and `.source-extracts/`.

### Format authority

`obsidian-vault/ic/` is the canonical worked example — match its frontmatter, type values,
section depth, and cross-linking. `config/wiki_schema.json` defines directory mapping and
baseline required fields. Where they differ, the `ic` vault wins.

### 1. Resolve scope and source files

List source files for the target department(s):
```
find "O:/brooker_database/{dept}" -type f
```
Skip pure image files (`.jpg`, `.png`) — they carry no extractable knowledge.
For `ic`, the vault is already populated — only process source files not already covered
by an existing article (check `obsidian-vault/ic/index.md`).

### 2. Extract source content

Run the batch extractor (converts docx/pdf/xlsx/pptx → markdown):
```
python scripts/extract_sources.py {dept}
```
Output lands in `.source-extracts/{dept}/` (gitignored). For any file the script cannot
handle, fall back to the `anthropic-skills:pdf` / `:docx` / `:xlsx` / `:pptx` skills.
Read the extracted markdown — do not author articles from filenames alone.

### 3. Classify content into article types

| Type | Directory | When |
|------|-----------|------|
| `concept` | `concepts/` | Policies, frameworks, doctrines, recurring domain knowledge |
| `decision_log` | `decisions/` | Board/committee decisions, approvals, running objectives |
| `meeting_note` | `meeting-notes/` | Meeting minutes and decks |
| `entity` | `entities/` | Counterparties, funds, facilities, instruments, people, org units |
| `trend` | `trends/` | Dashboards, time-series snapshots, periodic metrics |

One source document usually yields MULTIPLE articles — decompose fully. A single board
deck may produce one `meeting_note`, several `decision_log` articles, and several
`entity` articles.

### 4. Author wiki articles

Write each article to `obsidian-vault/{dept}/{directory}/{slug}.md`.

**Frontmatter** (required: `title`, `type`, `department`, `related`, `created`, `updated`,
`tags`; add `sources`, `confidence`, `coverage`, and type-specific fields like `status`,
`entity_type`, `source_file`, `first_seen`/`last_seen` as the `ic` examples do):
```yaml
---
title: "Human Readable Title"
type: "concept"            # concept | decision_log | meeting_note | entity | trend
department: "{dept}"
sources: ["Source File.docx"]
related: ["other-article-slug"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"         # high | medium | low
coverage: "high"
tags: ["{dept}", "type-keyword", "topic"]
---
```

**Body:** H1 title, then sections appropriate to the type (see `obsidian-vault/ic/`
examples and `config/wiki_schema.json` `article_types`). Use tables for metrics,
timelines, and key facts. Cross-link related articles inline with `[[slug]]`.

**Rules:**
- Filenames are lowercase kebab-case slugs (`{date}-{slug}.md` for decisions/meetings).
- Every claim must be traceable to a source — cite the source file.
- Thai-language sources (hr, legal): author articles in English, preserve key Thai terms.
- Low-value transactional files (receipts, tickets): one light `entity` note, no full
  decomposition.

### 5. Update index.md and log.md

- Create/update `obsidian-vault/{dept}/index.md` — link every new article, grouped by
  section, matching the `ic/index.md` layout.
- Append `obsidian-vault/{dept}/log.md` with a dated entry:
  `## [YYYY-MM-DD] ingest | <N> articles from brooker_database/{dept}`.

### 6. Register sources in document_inventory.json

Add one entry per source file to `config/document_inventory.json`:
```json
{
  "id": "doc_{dept}_{slug}",
  "title": "Source Title",
  "ownerDept": "{dept}",
  "tier": "policy",
  "vaultPath": "obsidian-vault/{dept}/{dir}/{slug}.md",
  "qdrantCollection": "{dept}_docs",
  "ingestSource": "file://O:/brooker_database/{dept}/{filename}",
  "frequency": "annual",
  "crossReadAccess": []
}
```

**Tier mapping** (`tier` enum: `policy`, `report`, `tracker`, `narrative`):

| Source kind | tier |
|-------------|------|
| Policy, agreement, template, legal opinion, contract | `policy` |
| Audited report, periodic (weekly/monthly/quarterly) report | `report` |
| Spreadsheet dashboard / portfolio tracker (`.xlsx`) | `tracker` |
| Meeting doc, deck, speech, retreat pack, event material | `narrative` |

Validate the result against `config/document_inventory.schema.json`.

### 7. Self-check and commit

- Every article has complete frontmatter and at least one `sources` entry.
- No orphan articles (each is linked from `index.md`).
- `[[links]]` resolve to real files.
- Run `python scripts/validate_config.py` if it covers the inventory.
- Commit per department: `feat(wiki): {dept} knowledge base from brooker_database`.

### Common mistakes

- Authoring from filenames without reading extracted content — always extract first.
- One giant article per file instead of decomposing — decompose fully.
- Forgetting `document_inventory.json` registration — the wiki is not "done" until
  every source is registered.
- Writing into `O:\brooker_database` — it is read-only corporate data.
