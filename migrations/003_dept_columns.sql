-- migrations/003_dept_columns.sql
-- Stage 6: Add department scoping columns for RBAC enforcement
-- Every gateway query MUST include WHERE dept = $1

ALTER TABLE staging_proposals
  ADD COLUMN IF NOT EXISTS dept VARCHAR(50) NOT NULL DEFAULT 'cac';

ALTER TABLE escalations
  ADD COLUMN IF NOT EXISTS dept VARCHAR(50) NOT NULL DEFAULT 'cac';

ALTER TABLE approval_decisions
  ADD COLUMN IF NOT EXISTS dept VARCHAR(50) NOT NULL DEFAULT 'cac';

CREATE INDEX IF NOT EXISTS idx_staging_proposals_dept
  ON staging_proposals(dept);
CREATE INDEX IF NOT EXISTS idx_staging_proposals_dept_status
  ON staging_proposals(dept, status);
CREATE INDEX IF NOT EXISTS idx_escalations_dept
  ON escalations(dept);
CREATE INDEX IF NOT EXISTS idx_approval_decisions_dept
  ON approval_decisions(dept);
