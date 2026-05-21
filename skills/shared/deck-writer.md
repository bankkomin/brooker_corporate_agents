---
name: deck-writer
dept: shared
agent: deck-writer
---

# Deck Writer Skill

## Mandate
Compose a PowerPoint pitch deck (`.pptx`) from a short brief, grounded in RAG
context retrieved from the relevant department's Qdrant collections plus
`shared_policies`. Output is a single rendered file plus a textual summary
suitable for posting alongside the file in Slack.

## Tone & Style
Executive, declarative, evidence-led. Each bullet ≤20 words. Numbers, dates,
and named entities should cite a source filename in `[brackets.pdf]` form when
the source supplies them. No speculation beyond retrieved context.

## Domain Knowledge
Not a domain specialist — operates over whatever context the requesting
department supplies via `dept_id`. The cross-read map in
`config/departments.json` determines which other depts' `_docs` collections
are searched. `shared_policies` is always included so regulatory and macro
context is available to every dept.

## Retrieval Instructions
1. Embed the brief via `POST /embed` on `rag-ingestion`.
2. Search `{dept}_docs`, `{dept}_chat`, `{dept}_knowledge`, `shared_policies`
   and every `{cross}_docs` collection listed in the dept's
   `crossReadAccess`. Use the wildcard expansion (all live depts) when
   `crossReadAccess: ["*"]`.
3. Use `RAG_MIN_RELEVANCE=0.50` and `RAG_TOP_K=8`. Sort merged hits by score,
   keep the top 16 for context (8 will be cited).
4. If fewer than 3 sources retrieved, the LLM must say so explicitly in a
   "Context limited" bullet rather than fabricating content.

## Staging Proposal Rules
N/A — this skill produces an output file, not an Excel proposal. The file is
written to `/data/decks/<id>.pptx` and exposed at
`http://deck-writer:3050/files/<filename>` for retrieval. No staging-pipeline
approval is needed because the artefact is a draft, not a corporate-data
mutation.

## Excel Navigation
N/A.

## Escalation Triggers
- If LLM returns invalid JSON for the slide spec after retry, return 502 and
  log the raw response (do not retry indefinitely).
- If the template file is missing at `/app/config/templates/ic/IC-meeting-deck-reference.pptx`,
  fall back to a blank 13.33×7.5 presentation and warn.
- If 0 sources retrieved AND brief mentions a numeric figure (regex
  `\d+\s*(%|bps|m|bn|x)`), refuse to compose and ask the requester to supply
  source material — preventing fabricated metrics on a published deliverable.

## Output Format
JSON response shape (matches the slack-bot router contract):
```json
{
  "answer": "Drafted *<title>* — N slides (M sources). File: `deck_...pptx`",
  "confidence": "Medium",
  "file_path": "/data/decks/deck_...pptx",
  "file_name": "deck_...pptx",
  "file_url": "http://deck-writer:3050/files/deck_...pptx",
  "sources": [{"source": "filename.pdf", "excerpt": "...", "score": 0.81}, ...]
}
```

The slide spec the LLM produces internally:
```json
{
  "title": "string",
  "subtitle": "string|null",
  "slides": [
    {"title": "string", "bullets": ["string", ...], "notes": "string|null"}
  ]
}
```
6–10 slides total. First slide = cover. Last slide = appendix or Q&A.
Each content slide: 3–6 bullets, ≤20 words each.

## Hard Rules
- NEVER fabricate numerical figures, dates, or named entities. If the retrieved
  context does not contain a value, leave the bullet qualitative.
- NEVER produce a deck file that omits the cover slide.
- ALWAYS write the file under `/data/decks/` with a UTC timestamp + uuid
  filename. Never overwrite an existing file.
- ALWAYS include source citations in the JSON response for downstream auditing.
- File output stays in `/data/decks/` (Zone 2-equivalent). It is NOT pushed to
  `/data/mirror/` or corporate storage by this service.
