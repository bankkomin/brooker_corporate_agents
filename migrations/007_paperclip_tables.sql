-- migrations/007_paperclip_tables.sql
-- Paperclip service tables for Stage 7

BEGIN;

-- Department registry
CREATE TABLE IF NOT EXISTS paperclip_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    slack_channel VARCHAR(100) NOT NULL,
    hod_email VARCHAR(200) NOT NULL,
    escalation_rules JSONB DEFAULT '{}',
    data_zone JSONB NOT NULL,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent registry (FK to departments)
CREATE TABLE IF NOT EXISTS paperclip_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id UUID NOT NULL REFERENCES paperclip_departments(id),
    agent_name VARCHAR(100) NOT NULL,
    agent_role VARCHAR(20) NOT NULL CHECK (agent_role IN ('orchestrator', 'specialist', 'worker')),
    worker_type VARCHAR(20) CHECK (worker_type IN ('claude_code', 'claude_sdk', 'human', 'stub')),
    endpoint_url VARCHAR(500),
    skills JSONB DEFAULT '[]',
    data_scope JSONB DEFAULT '{}',
    permissions JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'pending')),
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    last_heartbeat TIMESTAMPTZ,
    UNIQUE(department_id, agent_name)
);

-- Ticket tracking
CREATE TABLE IF NOT EXISTS paperclip_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id VARCHAR(20) UNIQUE NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('query', 'proposal', 'escalation', 'skill_task')),
    department VARCHAR(50) NOT NULL REFERENCES paperclip_departments(name),
    agent VARCHAR(100) NOT NULL,
    interaction_id UUID,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN (
        'open', 'in_progress', 'pending_approval',
        'completed', 'rejected', 'escalated',
        'pending_human', 'failed'
    )),
    payload JSONB NOT NULL,
    result JSONB,
    assigned_worker VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tickets_dept_status ON paperclip_tickets(department, status);
CREATE INDEX idx_tickets_type_created ON paperclip_tickets(type, created_at);
CREATE INDEX idx_agents_dept_status ON paperclip_agents(department_id, status);

-- Seed CAC department
INSERT INTO paperclip_departments (name, display_name, slack_channel, hod_email, data_zone, escalation_rules)
VALUES (
    'cac',
    'Capital Allocation & ALCO Committee',
    '#cac-committee',
    'cfo@company.com',
    '{"mirror": "/data/mirror/", "staging": "/data/staging/", "qdrant_prefix": "cac_", "qdrant_collections": ["cac_docs", "cac_chat", "cac_knowledge"]}',
    '{"covenant_ratio_threshold_pct": 10, "capital_request_delegation_check": true, "liquidity_minimum_check": true}'
) ON CONFLICT (name) DO NOTHING;

-- Seed CAC agents (get dept id)
DO $$
DECLARE
    dept_id UUID;
BEGIN
    SELECT id INTO dept_id FROM paperclip_departments WHERE name = 'cac';

    -- CFO Agent (cac-orchestrator)
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, endpoint_url, skills, data_scope, permissions)
    VALUES (dept_id, 'cfo-agent', 'orchestrator', 'http://cac-orchestrator:3001/health',
        '["shared/escalation-protocol", "shared/citation-format", "shared/cfo-agent", "shared/excel-navigation", "shared/rag-retrieval"]',
        '{"collections": ["cac_docs", "cac_chat", "cac_knowledge"], "mirror_paths": ["/data/mirror/"]}',
        '{"can_stage": true, "can_escalate": true}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    -- Specialist agents
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, skills, permissions)
    VALUES
        (dept_id, 'liquidity-agent', 'specialist',
         '["cac/liquidity-analysis", "shared/escalation-protocol", "shared/citation-format"]',
         '{"can_stage": true, "staging_tabs": ["Liquidity"]}'),
        (dept_id, 'capital-agent', 'specialist',
         '["cac/capital-allocation", "cac/covenant-monitoring", "shared/escalation-protocol", "shared/citation-format"]',
         '{"can_stage": true, "staging_tabs": ["Capital Allocation"]}'),
        (dept_id, 'alm-agent', 'specialist',
         '["cac/alm-review", "shared/escalation-protocol", "shared/citation-format"]',
         '{"can_stage": true, "staging_tabs": ["ALM"]}'),
        (dept_id, 'funding-agent', 'specialist',
         '["cac/funding-facilities", "shared/escalation-protocol", "shared/citation-format"]',
         '{"can_stage": true, "staging_tabs": ["Funding Facilities"]}'),
        (dept_id, 'escalation-agent', 'specialist',
         '["shared/escalation-protocol"]',
         '{"can_stage": false, "can_escalate": true}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    -- OpenClaw worker (stub)
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, worker_type, skills, permissions)
    VALUES (dept_id, 'openclaw', 'worker', 'stub',
        '["shared/escalation-protocol", "shared/citation-format"]',
        '{"can_stage": false}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;
END $$;

COMMIT;
