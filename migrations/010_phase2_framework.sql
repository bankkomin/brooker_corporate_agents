-- Migration 010: Phase 2 Framework Infrastructure
-- Adds: agent_knowledge_gaps, agent_skill_proposals, reflection_runs tables
-- Adds: agent_performance view (computed signal_strength from approval_decisions)

CREATE TABLE IF NOT EXISTS agent_knowledge_gaps (
  id              BIGSERIAL PRIMARY KEY,
  dept_id         TEXT NOT NULL,
  agent_id        TEXT NOT NULL,
  query           TEXT NOT NULL,
  hit_count       INT NOT NULL,
  llm_self_report TEXT,
  expected_doc_type TEXT,
  resolved_at     TIMESTAMPTZ,
  resolved_by     TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_knowledge_gaps_dept_unresolved
  ON agent_knowledge_gaps(dept_id) WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS agent_skill_proposals (
  id              BIGSERIAL PRIMARY KEY,
  dept_id         TEXT NOT NULL,
  agent_id        TEXT NOT NULL,
  skill_path      TEXT NOT NULL,
  trigger         TEXT NOT NULL,
  evidence        JSONB NOT NULL,
  status          TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'hod_review', 'approved', 'rejected')),
  proposed_diff   TEXT,
  hod_decision_at TIMESTAMPTZ,
  decided_by      TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_skill_proposals_status ON agent_skill_proposals(status);

CREATE TABLE IF NOT EXISTS reflection_runs (
  id           BIGSERIAL PRIMARY KEY,
  dept_id      TEXT NOT NULL,
  started_at   TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  status       TEXT NOT NULL,
  error        TEXT,
  stats        JSONB
);
CREATE INDEX IF NOT EXISTS idx_reflection_runs_dept_started ON reflection_runs(dept_id, started_at DESC);

CREATE OR REPLACE VIEW agent_performance AS
SELECT
  ai.dept_id,
  ai.agent_id,
  sp.id AS proposal_id,
  ad.action,
  CASE ad.action
    WHEN 'approved' THEN 1.0
    WHEN 'edited' THEN
      CASE
        WHEN sp.proposed_value ~ '^-?[0-9]+\.?[0-9]*$'
         AND ad.edited_value ~ '^-?[0-9]+\.?[0-9]*$'
        THEN 0.5 + 0.5 * (1.0 - LEAST(1.0,
          ABS(sp.proposed_value::numeric - ad.edited_value::numeric)
          / NULLIF(GREATEST(ABS(sp.proposed_value::numeric), 1), 0)
        ))
        ELSE 0.5  -- non-numeric edit: assume moderate signal
      END
    WHEN 'rejected' THEN 0.0
  END AS signal_strength,
  ad.rejection_reason,
  ad.edited_value,
  ad.created_at
FROM approval_decisions ad
JOIN staging_proposals  sp ON sp.id = ad.proposal_id
JOIN agent_interactions ai ON ai.id = sp.interaction_id;
