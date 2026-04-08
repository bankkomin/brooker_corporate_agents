-- migrations/001_initial_schema.sql
-- Corporate AI Agent System — Initial Schema
-- 7 tables: agent_interactions, staging_proposals, approval_decisions,
--           sync_log, ingested_documents, escalations, email_log

BEGIN;

-- 1. Agent Interactions (query log)
CREATE TABLE agent_interactions (
    id                   BIGSERIAL PRIMARY KEY,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id              VARCHAR(50) NOT NULL,
    channel              VARCHAR(100) NOT NULL,
    thread_ts            VARCHAR(50),
    query                TEXT NOT NULL,
    intent               VARCHAR(50),
    response             TEXT,
    sources_count        INT,
    escalation           BOOLEAN DEFAULT FALSE,
    staging_proposal_id  VARCHAR(50),
    confidence           NUMERIC(4,2),
    processing_ms        INT,
    paperclip_ticket_id  VARCHAR(50)
);
CREATE INDEX idx_agent_interactions_created_at ON agent_interactions(created_at DESC);
CREATE INDEX idx_agent_interactions_user_id ON agent_interactions(user_id);

-- 2. Staging Proposals (agent change proposals)
CREATE TABLE staging_proposals (
    id              VARCHAR(50) PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent           VARCHAR(100),
    file            VARCHAR(500),
    tab             VARCHAR(100),
    cell            VARCHAR(20),
    old_value       TEXT,
    new_value       TEXT,
    source          TEXT,
    confidence      NUMERIC(4,2),
    reasoning       TEXT,
    status          VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'synced')),
    interaction_id  BIGINT REFERENCES agent_interactions(id)
);
CREATE INDEX idx_staging_proposals_status ON staging_proposals(status);
CREATE INDEX idx_staging_proposals_created_at ON staging_proposals(created_at DESC);

-- 3. Approval Decisions (HOD decisions)
CREATE TABLE approval_decisions (
    id               BIGSERIAL PRIMARY KEY,
    decided_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    proposal_id      VARCHAR(50) REFERENCES staging_proposals(id),
    decision         VARCHAR(20) NOT NULL CHECK (decision IN ('approved', 'rejected', 'edited')),
    decided_by       VARCHAR(100) NOT NULL,
    edited_value     TEXT,
    rejection_reason TEXT,
    synced_at        TIMESTAMPTZ,
    sync_verified    BOOLEAN
);
CREATE INDEX idx_approval_decisions_proposal_id ON approval_decisions(proposal_id);
CREATE INDEX idx_approval_decisions_decided_at ON approval_decisions(decided_at DESC);

-- 4. Sync Log (mirror and sync-back operations)
CREATE TABLE sync_log (
    id              BIGSERIAL PRIMARY KEY,
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    direction       VARCHAR(10) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    files_updated   INT,
    files_checked   INT,
    duration_ms     INT,
    status          VARCHAR(20),
    error           TEXT
);
CREATE INDEX idx_sync_log_synced_at ON sync_log(synced_at DESC);
CREATE INDEX idx_sync_log_direction ON sync_log(direction);

-- 5. Ingested Documents (document registry for dedup)
CREATE TABLE ingested_documents (
    id                BIGSERIAL PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filename          VARCHAR(500) NOT NULL,
    dept              VARCHAR(50),
    doc_type          VARCHAR(100),
    uploader_id       VARCHAR(50),
    channel           VARCHAR(100),
    chunks_count      INT,
    chroma_collection VARCHAR(100),
    file_hash         VARCHAR(64) UNIQUE
);
CREATE INDEX idx_ingested_documents_file_hash ON ingested_documents(file_hash);
CREATE INDEX idx_ingested_documents_created_at ON ingested_documents(created_at DESC);

-- 6. Escalations (breach alerts)
CREATE TABLE escalations (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interaction_id      BIGINT REFERENCES agent_interactions(id),
    severity            VARCHAR(20),
    trigger_type        VARCHAR(100),
    detail              TEXT,
    paperclip_ticket_id VARCHAR(50),
    resolved_at         TIMESTAMPTZ,
    resolved_by         VARCHAR(50)
);
CREATE INDEX idx_escalations_created_at ON escalations(created_at DESC);
CREATE INDEX idx_escalations_severity ON escalations(severity);

-- 7. Email Log (delivery tracking)
CREATE TABLE email_log (
    id              BIGSERIAL PRIMARY KEY,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recipient       VARCHAR(200) NOT NULL,
    event_type      VARCHAR(50) NOT NULL,
    proposal_id     VARCHAR(50),
    dept            VARCHAR(50),
    subject         TEXT,
    delivery_status VARCHAR(20) CHECK (delivery_status IN ('sent', 'delivered', 'failed', 'bounced', 'pending')),
    error           TEXT,
    retry_count     INT DEFAULT 0
);
CREATE INDEX idx_email_log_sent_at ON email_log(sent_at DESC);
CREATE INDEX idx_email_log_recipient ON email_log(recipient);
CREATE INDEX idx_email_log_delivery_status ON email_log(delivery_status);

COMMIT;
