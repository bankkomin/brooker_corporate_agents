-- migrations/008_agent_access.sql
-- Bridge table: which brooker_employee employees can access which paperclip agent departments.
-- employee_id references the UUID PK in brooker_employee.public.employees.
-- department_name references paperclip_departments.name in this DB.

BEGIN;

CREATE TABLE IF NOT EXISTS agent_access (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID NOT NULL,                -- FK to brooker_employee.public.employees.id
    employee_email  VARCHAR(255) NOT NULL,         -- denormalized for quick lookups without cross-DB join
    department_name VARCHAR(50) NOT NULL REFERENCES paperclip_departments(name),
    -- Permissions
    can_query       BOOLEAN NOT NULL DEFAULT TRUE, -- can ask AI agents questions
    can_approve     BOOLEAN NOT NULL DEFAULT FALSE,-- can approve/reject staging proposals
    can_view_proposals BOOLEAN NOT NULL DEFAULT TRUE, -- can see proposals dashboard
    can_escalate    BOOLEAN NOT NULL DEFAULT FALSE,-- can trigger manual escalations
    -- Audit
    granted_by      VARCHAR(255),                  -- email of who granted access
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ,                   -- NULL = active, set = revoked
    UNIQUE(employee_id, department_name)
);

CREATE INDEX idx_agent_access_employee ON agent_access(employee_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_agent_access_dept ON agent_access(department_name) WHERE revoked_at IS NULL;
CREATE INDEX idx_agent_access_email ON agent_access(employee_email) WHERE revoked_at IS NULL;

-- Seed access for Varut (CEO), Min Khant Soe (Senior AI Dev), Karin (Trading Strategy Dev)
-- Using emails as stable identifiers; employee_id will be resolved at runtime from brooker_employee DB.
-- For now we use deterministic UUIDs as placeholders — the auth bridge resolves by email.
INSERT INTO agent_access (employee_id, employee_email, department_name, can_query, can_approve, can_view_proposals, can_escalate, granted_by)
VALUES
    -- Varut Bulakul — CEO, full access
    ('00000000-0000-0000-0000-000000000001', 'varut@brookergroup.com', 'cac',
     TRUE, TRUE, TRUE, TRUE, 'system'),
    -- Min Khant Soe — Senior AI Developer, query + view
    ('00000000-0000-0000-0000-000000000002', 's.minkhant@brookergroup.com', 'cac',
     TRUE, FALSE, TRUE, FALSE, 'system'),
    -- Karin Komin — Trading Strategy Developer, query + view
    ('00000000-0000-0000-0000-000000000003', 'karin@brookergroup.com', 'cac',
     TRUE, FALSE, TRUE, FALSE, 'system')
ON CONFLICT (employee_id, department_name) DO NOTHING;

COMMIT;
