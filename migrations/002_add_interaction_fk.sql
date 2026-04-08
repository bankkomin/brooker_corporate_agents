-- migrations/002_add_interaction_fk.sql
-- Add index on staging_proposals.interaction_id for FK query performance

BEGIN;

CREATE INDEX IF NOT EXISTS idx_staging_proposals_interaction_id
ON staging_proposals(interaction_id);

COMMIT;
