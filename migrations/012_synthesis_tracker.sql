-- B4 — Entity-mention tracking for auto-synthesis proposals.
--
-- Each ingested document chunk that mentions a named entity (concept,
-- regulation, instrument, counterparty) generates a row here. When the
-- distinct-source-document count for a given (entity, dept) crosses a
-- per-dept threshold (config/synthesis_thresholds.json), the
-- synthesis_proposer drafts a concept note and writes a vault staging
-- manifest for HOD approval.
--
-- Indexing optimizes the threshold query
--   SELECT entity, dept, COUNT(DISTINCT source_doc)
--   FROM entity_mentions
--   GROUP BY entity, dept

CREATE TABLE IF NOT EXISTS entity_mentions (
    id BIGSERIAL PRIMARY KEY,
    entity TEXT NOT NULL,                       -- canonical kebab-case slug
    entity_display_name TEXT NOT NULL,          -- original casing
    entity_kind TEXT NOT NULL CHECK (
        entity_kind IN ('company', 'instrument', 'regulation', 'concept', 'person', 'other')
    ),
    source_doc TEXT NOT NULL,                   -- vault-relative or O:\ path
    dept TEXT NOT NULL,
    chunk_id TEXT,                              -- Qdrant point id, when available
    mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uniq_entity_source UNIQUE (entity, source_doc, chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity_dept
    ON entity_mentions (entity, dept);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_dept_mentioned
    ON entity_mentions (dept, mentioned_at DESC);

-- Tracks which (entity, dept) pairs already have a concept note proposed
-- or accepted, so the proposer doesn't re-propose every nightly run.
CREATE TABLE IF NOT EXISTS synthesis_state (
    entity TEXT NOT NULL,
    dept TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('not_proposed', 'proposed_pending', 'proposed_accepted', 'proposed_rejected', 'manual_canonical')
    ),
    proposal_id TEXT,                           -- chg_XXXX, when a manifest was written
    last_changed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (entity, dept)
);
