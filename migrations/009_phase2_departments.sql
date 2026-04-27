-- migrations/009_phase2_departments.sql
-- Phase 2: Insert 7 new departments and their agents

BEGIN;

-- ─────────────────────────────────────────────
-- DEPARTMENT INSERTS
-- ─────────────────────────────────────────────

INSERT INTO paperclip_departments (name, display_name, slack_channel, hod_email, data_zone, escalation_rules)
VALUES
    (
        'risk',
        'Risk Committee',
        '#risk-committee',
        'cro@company.com',
        '{"mirror": "/data/mirror/risk/", "staging": "/data/staging/", "qdrant_prefix": "risk_", "qdrant_collections": ["risk_docs", "risk_chat", "risk_knowledge"]}',
        '{"var_breach_threshold_pct": 10, "npl_ratio_threshold_pct": 3, "operational_loss_threshold": true}'
    ),
    (
        'legal',
        'Legal & Compliance',
        '#legal-committee',
        'clo@company.com',
        '{"mirror": "/data/mirror/legal/", "staging": "/data/staging/", "qdrant_prefix": "legal_", "qdrant_collections": ["legal_docs", "legal_chat", "legal_knowledge"]}',
        '{"open_breach_threshold": 0, "overdue_remediation_threshold": 5, "regulatory_return_alert_days": 14}'
    ),
    (
        'invest',
        'Investment Committee',
        '#invest-committee',
        'cio@company.com',
        '{"mirror": "/data/mirror/investments/", "staging": "/data/staging/", "qdrant_prefix": "invest_", "qdrant_collections": ["invest_docs", "invest_chat", "invest_knowledge"]}',
        '{"nav_drop_threshold_pct": 5, "level3_assets_limit_pct": 20, "cash_drag_limit_pct": 10}'
    ),
    (
        'ops',
        'Operations',
        '#ops-committee',
        'coo@company.com',
        '{"mirror": "/data/mirror/operations/", "staging": "/data/staging/", "qdrant_prefix": "ops_", "qdrant_collections": ["ops_docs", "ops_chat", "ops_knowledge"]}',
        '{"sla_compliance_minimum_pct": 95, "vendor_breach_threshold": 3, "safety_incident_threshold": 0}'
    ),
    (
        'hr',
        'Human Resources',
        '#hr-committee',
        'chro@company.com',
        '{"mirror": "/data/mirror/hr/", "staging": "/data/staging/", "qdrant_prefix": "hr_", "qdrant_collections": ["hr_docs", "hr_chat", "hr_knowledge"]}',
        '{"attrition_threshold_pct": 10, "open_grievance_threshold": 5, "salary_band_compliance_minimum_pct": 95}'
    ),
    (
        'it',
        'Information Technology',
        '#it-committee',
        'cto@company.com',
        '{"mirror": "/data/mirror/it/", "staging": "/data/staging/", "qdrant_prefix": "it_", "qdrant_collections": ["it_docs", "it_chat", "it_knowledge"]}',
        '{"availability_minimum_pct": 99.9, "critical_vuln_threshold": 0, "change_failure_rate_threshold_pct": 5}'
    ),
    (
        'ceo',
        'CEO Office',
        '#ceo-office',
        'ceo@company.com',
        '{"mirror": "/data/mirror/", "staging": "/data/staging/", "qdrant_prefix": "shared_", "qdrant_collections": ["shared_policies"]}',
        '{}'
    )
ON CONFLICT (name) DO NOTHING;

-- ─────────────────────────────────────────────
-- AGENT INSERTS
-- ─────────────────────────────────────────────

DO $$
DECLARE
    risk_id   UUID;
    legal_id  UUID;
    invest_id UUID;
    ops_id    UUID;
    hr_id     UUID;
    it_id     UUID;
    ceo_id    UUID;
BEGIN
    SELECT id INTO risk_id   FROM paperclip_departments WHERE name = 'risk';
    SELECT id INTO legal_id  FROM paperclip_departments WHERE name = 'legal';
    SELECT id INTO invest_id FROM paperclip_departments WHERE name = 'invest';
    SELECT id INTO ops_id    FROM paperclip_departments WHERE name = 'ops';
    SELECT id INTO hr_id     FROM paperclip_departments WHERE name = 'hr';
    SELECT id INTO it_id     FROM paperclip_departments WHERE name = 'it';
    SELECT id INTO ceo_id    FROM paperclip_departments WHERE name = 'ceo';

    -- ── RISK ─────────────────────────────────
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, endpoint_url, skills, data_scope, permissions)
    VALUES (risk_id, 'cro-agent', 'orchestrator', 'http://risk-orchestrator:3001/health',
        '["shared/escalation-protocol", "shared/citation-format", "shared/cro-agent", "shared/excel-navigation", "shared/rag-retrieval"]',
        '{"collections": ["risk_docs", "risk_chat", "risk_knowledge"], "mirror_paths": ["/data/mirror/risk/"]}',
        '{"can_stage": true, "can_escalate": true}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, skills, data_scope, permissions)
    VALUES
        (risk_id, 'credit-risk-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["risk_docs", "risk_knowledge"], "mirror_paths": ["/data/mirror/risk/"]}',
         '{"can_stage": true, "staging_tabs": ["Credit Risk"]}'),
        (risk_id, 'market-risk-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["risk_docs", "risk_knowledge"], "mirror_paths": ["/data/mirror/risk/"]}',
         '{"can_stage": true, "staging_tabs": ["Market Risk"]}'),
        (risk_id, 'operational-risk-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["risk_docs", "risk_knowledge"], "mirror_paths": ["/data/mirror/risk/"]}',
         '{"can_stage": true, "staging_tabs": ["Operational Risk"]}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    -- ── LEGAL ────────────────────────────────
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, endpoint_url, skills, data_scope, permissions)
    VALUES (legal_id, 'clo-agent', 'orchestrator', 'http://legal-orchestrator:3001/health',
        '["shared/escalation-protocol", "shared/citation-format", "shared/clo-agent", "shared/excel-navigation", "shared/rag-retrieval"]',
        '{"collections": ["legal_docs", "legal_chat", "legal_knowledge"], "mirror_paths": ["/data/mirror/legal/"]}',
        '{"can_stage": true, "can_escalate": true}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, skills, data_scope, permissions)
    VALUES
        (legal_id, 'compliance-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["legal_docs", "legal_knowledge"], "mirror_paths": ["/data/mirror/legal/"]}',
         '{"can_stage": true, "staging_tabs": ["Compliance"]}'),
        (legal_id, 'regulatory-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["legal_docs", "legal_knowledge"], "mirror_paths": ["/data/mirror/legal/"]}',
         '{"can_stage": true, "staging_tabs": ["Regulatory"]}'),
        (legal_id, 'contract-review-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["legal_docs", "legal_knowledge"], "mirror_paths": ["/data/mirror/legal/"]}',
         '{"can_stage": true, "staging_tabs": ["Contracts"]}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    -- ── INVEST ───────────────────────────────
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, endpoint_url, skills, data_scope, permissions)
    VALUES (invest_id, 'cio-agent', 'orchestrator', 'http://invest-orchestrator:3001/health',
        '["shared/escalation-protocol", "shared/citation-format", "shared/cio-agent", "shared/excel-navigation", "shared/rag-retrieval"]',
        '{"collections": ["invest_docs", "invest_chat", "invest_knowledge"], "mirror_paths": ["/data/mirror/investments/"]}',
        '{"can_stage": true, "can_escalate": true}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, skills, data_scope, permissions)
    VALUES
        (invest_id, 'portfolio-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["invest_docs", "invest_knowledge"], "mirror_paths": ["/data/mirror/investments/"]}',
         '{"can_stage": true, "staging_tabs": ["Portfolio"]}'),
        (invest_id, 'valuation-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["invest_docs", "invest_knowledge"], "mirror_paths": ["/data/mirror/investments/"]}',
         '{"can_stage": true, "staging_tabs": ["Valuation"]}'),
        (invest_id, 'due-diligence-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["invest_docs", "invest_knowledge"], "mirror_paths": ["/data/mirror/investments/"]}',
         '{"can_stage": true, "staging_tabs": ["Due Diligence"]}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    -- ── OPS ──────────────────────────────────
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, endpoint_url, skills, data_scope, permissions)
    VALUES (ops_id, 'coo-agent', 'orchestrator', 'http://ops-orchestrator:3001/health',
        '["shared/escalation-protocol", "shared/citation-format", "shared/coo-agent", "shared/excel-navigation", "shared/rag-retrieval"]',
        '{"collections": ["ops_docs", "ops_chat", "ops_knowledge"], "mirror_paths": ["/data/mirror/operations/"]}',
        '{"can_stage": true, "can_escalate": true}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, skills, data_scope, permissions)
    VALUES
        (ops_id, 'process-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["ops_docs", "ops_knowledge"], "mirror_paths": ["/data/mirror/operations/"]}',
         '{"can_stage": true, "staging_tabs": ["Process"]}'),
        (ops_id, 'vendor-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["ops_docs", "ops_knowledge"], "mirror_paths": ["/data/mirror/operations/"]}',
         '{"can_stage": true, "staging_tabs": ["Vendor"]}'),
        (ops_id, 'facilities-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["ops_docs", "ops_knowledge"], "mirror_paths": ["/data/mirror/operations/"]}',
         '{"can_stage": true, "staging_tabs": ["Facilities"]}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    -- ── HR ───────────────────────────────────
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, endpoint_url, skills, data_scope, permissions)
    VALUES (hr_id, 'chro-agent', 'orchestrator', 'http://hr-orchestrator:3001/health',
        '["shared/escalation-protocol", "shared/citation-format", "shared/chro-agent", "shared/excel-navigation", "shared/rag-retrieval"]',
        '{"collections": ["hr_docs", "hr_chat", "hr_knowledge"], "mirror_paths": ["/data/mirror/hr/"]}',
        '{"can_stage": true, "can_escalate": true}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, skills, data_scope, permissions)
    VALUES
        (hr_id, 'talent-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["hr_docs", "hr_knowledge"], "mirror_paths": ["/data/mirror/hr/"]}',
         '{"can_stage": true, "staging_tabs": ["Talent"]}'),
        (hr_id, 'compensation-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["hr_docs", "hr_knowledge"], "mirror_paths": ["/data/mirror/hr/"]}',
         '{"can_stage": true, "staging_tabs": ["Compensation"]}'),
        (hr_id, 'policy-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["hr_docs", "hr_knowledge"], "mirror_paths": ["/data/mirror/hr/"]}',
         '{"can_stage": true, "staging_tabs": ["Policy"]}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    -- ── IT ───────────────────────────────────
    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, endpoint_url, skills, data_scope, permissions)
    VALUES (it_id, 'cto-agent', 'orchestrator', 'http://it-orchestrator:3001/health',
        '["shared/escalation-protocol", "shared/citation-format", "shared/cto-agent", "shared/excel-navigation", "shared/rag-retrieval"]',
        '{"collections": ["it_docs", "it_chat", "it_knowledge"], "mirror_paths": ["/data/mirror/it/"]}',
        '{"can_stage": true, "can_escalate": true}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    INSERT INTO paperclip_agents (department_id, agent_name, agent_role, skills, data_scope, permissions)
    VALUES
        (it_id, 'infrastructure-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["it_docs", "it_knowledge"], "mirror_paths": ["/data/mirror/it/"]}',
         '{"can_stage": true, "staging_tabs": ["Infrastructure"]}'),
        (it_id, 'security-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["it_docs", "it_knowledge"], "mirror_paths": ["/data/mirror/it/"]}',
         '{"can_stage": true, "staging_tabs": ["Security"]}'),
        (it_id, 'devops-agent', 'specialist',
         '["shared/escalation-protocol", "shared/citation-format"]',
         '{"collections": ["it_docs", "it_knowledge"], "mirror_paths": ["/data/mirror/it/"]}',
         '{"can_stage": true, "staging_tabs": ["DevOps"]}')
    ON CONFLICT (department_id, agent_name) DO NOTHING;

    -- ── CEO (no specialist agents — escalation target only) ──
    -- No agent rows needed; CEO office receives escalations but runs no automated agents.

END $$;

COMMIT;
