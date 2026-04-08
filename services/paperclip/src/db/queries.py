"""SQL queries for Paperclip service.

All queries use parameterized placeholders ($1, $2, etc.) for asyncpg.
"""

# -- Tickets --

CREATE_TICKET = """
INSERT INTO paperclip_tickets (ticket_id, type, department, agent, interaction_id, payload)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING id, ticket_id, type, department, agent, status, payload, result,
          assigned_worker, created_at, updated_at
"""

GET_TICKET = """
SELECT id, ticket_id, type, department, agent, interaction_id, status,
       payload, result, assigned_worker, created_at, updated_at
FROM paperclip_tickets WHERE ticket_id = $1
"""

LIST_TICKETS = """
SELECT id, ticket_id, type, department, agent, status, payload, result,
       assigned_worker, created_at, updated_at
FROM paperclip_tickets
WHERE ($1::text IS NULL OR department = $1)
  AND ($2::text IS NULL OR type = $2)
  AND ($3::text IS NULL OR status = $3)
  AND ($4::text IS NULL OR agent = $4)
ORDER BY created_at DESC
LIMIT $5 OFFSET $6
"""

UPDATE_TICKET = """
UPDATE paperclip_tickets
SET status = COALESCE($2, status),
    result = COALESCE($3, result),
    assigned_worker = COALESCE($4, assigned_worker),
    updated_at = NOW()
WHERE ticket_id = $1
RETURNING id, ticket_id, type, department, agent, status, payload, result,
          assigned_worker, created_at, updated_at
"""

# -- Next ticket ID --

NEXT_TICKET_ID = """
SELECT COALESCE(
    MAX(CAST(SUBSTRING(ticket_id FROM 5) AS INTEGER)),
    0
) + 1 AS next_num
FROM paperclip_tickets
"""

# -- Departments --

CREATE_DEPARTMENT = """
INSERT INTO paperclip_departments (name, display_name, slack_channel, hod_email,
                                    escalation_rules, data_zone, config)
VALUES ($1, $2, $3, $4, $5, $6, $7)
RETURNING id, name, display_name, slack_channel, hod_email, data_zone, created_at
"""

LIST_DEPARTMENTS = """
SELECT d.id, d.name, d.display_name, d.slack_channel, d.hod_email, d.data_zone,
       d.created_at, COUNT(a.id) AS agent_count
FROM paperclip_departments d
LEFT JOIN paperclip_agents a ON a.department_id = d.id
GROUP BY d.id
ORDER BY d.name
"""

GET_DEPARTMENT = """
SELECT id, name, display_name, slack_channel, hod_email, escalation_rules,
       data_zone, config, created_at
FROM paperclip_departments WHERE name = $1
"""

# -- Agents --

REGISTER_AGENT = """
INSERT INTO paperclip_agents (department_id, agent_name, agent_role, worker_type,
                               endpoint_url, skills, data_scope, permissions)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (department_id, agent_name) DO UPDATE
SET agent_role = EXCLUDED.agent_role,
    worker_type = EXCLUDED.worker_type,
    endpoint_url = EXCLUDED.endpoint_url,
    skills = EXCLUDED.skills,
    data_scope = EXCLUDED.data_scope,
    permissions = EXCLUDED.permissions,
    status = 'active',
    last_heartbeat = NOW()
RETURNING id, agent_name, agent_role, worker_type, endpoint_url, skills, status, last_heartbeat
"""

LIST_AGENTS = """
SELECT a.agent_name, d.name AS department, a.agent_role, a.worker_type,
       a.endpoint_url, a.skills, a.status, a.last_heartbeat
FROM paperclip_agents a
JOIN paperclip_departments d ON d.id = a.department_id
WHERE d.name = $1
ORDER BY a.agent_role, a.agent_name
"""

DEREGISTER_AGENT = """
UPDATE paperclip_agents
SET status = 'inactive'
WHERE department_id = (SELECT id FROM paperclip_departments WHERE name = $1)
  AND agent_name = $2
RETURNING agent_name
"""

# -- Heartbeat --

UPDATE_HEARTBEAT = """
UPDATE paperclip_agents
SET last_heartbeat = NOW(), status = 'active'
WHERE agent_name = $1
  AND department_id = (SELECT id FROM paperclip_departments WHERE name = $2)
RETURNING agent_name, status, last_heartbeat
"""

GET_DEPARTMENT_ID = """
SELECT id FROM paperclip_departments WHERE name = $1
"""

LIST_HEARTBEATS = """
SELECT a.agent_name, d.name AS department, a.agent_role, a.endpoint_url,
       a.status, a.last_heartbeat,
       CASE
           WHEN a.last_heartbeat IS NULL THEN 'never_seen'
           WHEN NOW() - a.last_heartbeat > INTERVAL '120 seconds' THEN 'stale'
           ELSE 'healthy'
       END AS health
FROM paperclip_agents a
JOIN paperclip_departments d ON d.id = a.department_id
WHERE a.status = 'active'
ORDER BY d.name, a.agent_name
"""

MARK_STALE_AGENTS = """
-- 120s = stale for display (LIST_HEARTBEATS), 300s = mark inactive (this query)
-- Rationale: brief network blips shouldn't deregister agents; 5min is the hard cutoff
UPDATE paperclip_agents
SET status = 'inactive'
WHERE last_heartbeat < NOW() - INTERVAL '300 seconds'
  AND status = 'active'
  AND agent_role != 'worker'
RETURNING agent_name
"""
