---
name: paperclip-service
agent: devops
dept: shared
version: 1.0
---

## Mandate
Operational knowledge for the Paperclip service (port 3100) — the audit and orchestration hub for the entire agent system. This skill covers: service architecture, maintenance procedures, troubleshooting, department onboarding, and agent registration.

Paperclip does NOT:
- Execute agent logic (that is cac-orchestrator)
- Send emails (that is email-notifier)
- Write to corporate data (that is sync-back)
- Serve the approval UI (that is approval-ui, port 4000)

## Tone & Style
- Technical operations language: "endpoint", "heartbeat", "ticket lifecycle"
- Include exact URLs, ports, and table names when referencing infrastructure
- When troubleshooting, always check logs first: `docker logs cac-paperclip`

## Domain Knowledge

### Service Identity
- **Port:** 3100
- **Container:** cac-paperclip
- **Stack:** Python 3.11, FastAPI, asyncpg, httpx, structlog
- **Database:** PostgreSQL (shared with other services)
- **Authentication:** API key via `X-API-Key` header (env: `PAPERCLIP_API_KEY`)

### Architecture Overview
Paperclip is the central audit and event routing hub. It has five subsystems:

1. **Ticket Manager** — CRUD for PPC-XXXX tickets. Every agent query, staging proposal, and escalation creates a ticket.
2. **Heartbeat Registry** — Tracks agent health. Agents POST to `/heartbeat` every 60s. Stale after 120s display, inactive after 300s.
3. **Department Manager** — Registry of departments and their agents with data boundary enforcement.
4. **Event Router** — Receives webhooks from approval-ui, routes to sync-back + email-notifier with retry logic (3x exponential backoff).
5. **Worker Manager** — OpenClaw stub interface. Assigns tickets to workers. Currently stub mode (`worker_type: "stub"`).

### Database Tables
| Table | Purpose |
|-------|---------|
| `paperclip_departments` | Department registry (name, slack channel, HOD email, data zones) |
| `paperclip_agents` | Agent registry (per department, with skills, permissions, heartbeat) |
| `paperclip_tickets` | Ticket lifecycle tracking (PPC-XXXX IDs, status, payload) |

### Ticket Lifecycle
```
Open → InProgress → PendingApproval → Completed
                                    → Rejected
                  → Escalated → Completed
Open → PendingHuman → Completed
Any → Failed (on unrecoverable error)
```

### API Endpoints
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | None | Docker healthcheck |
| POST | `/tickets` | API key | Create ticket |
| PATCH | `/tickets/{id}` | API key | Update ticket status |
| GET | `/tickets/{id}` | API key | Get ticket details |
| GET | `/tickets` | API key | List/filter tickets |
| POST | `/heartbeat` | API key | Agent heartbeat registration |
| GET | `/heartbeats` | API key | List agents with health status |
| POST | `/webhooks/approval` | JWT/API key | Receive approval-ui events |
| POST | `/departments` | API key | Register new department |
| GET | `/departments` | API key | List departments |
| POST | `/departments/{dept}/agents` | API key | Register agent |
| GET | `/departments/{dept}/agents` | API key | List agents |
| DELETE | `/departments/{dept}/agents/{name}` | API key | Deregister agent |
| POST | `/workers/{agent}/assign` | API key | Assign ticket to worker |
| GET | `/workers/{agent}/status` | API key | Worker status |

### Event Routing Flows
**On approval (from approval-ui):**
1. Update ticket → "completed"
2. POST sync-back `/process-approved`
3. POST email-notifier `/notify/confirmed`

**On rejection:**
1. Update ticket → "rejected"
2. Move staging file to `/data/staging/rejected/`
3. POST email-notifier `/notify/confirmed` (with rejection)

**On deferral:**
1. Ticket stays "pending_approval"
2. No downstream action

**On escalation (from cac-orchestrator):**
1. Create escalation ticket
2. POST email-notifier `/notify/escalation`
3. POST slack-bot `/post-escalation` (#escalations channel)

## Retrieval Instructions
- Check `paperclip_tickets` table for audit trail of any interaction
- Check `paperclip_agents` table for current agent registrations and health
- Check `paperclip_departments` table for department configurations
- Cross-reference `ticket_id` with `agent_interactions` table via `interaction_id`

## Staging Proposal Rules
Paperclip does NOT create staging proposals. It tracks them via tickets:
- When cac-orchestrator creates a staging proposal, it also creates a Paperclip ticket (type: "proposal")
- The `payload.proposal_id` links to the staging manifest in `/data/staging/pending/`
- On approval webhook, Paperclip triggers sync-back and moves the file

## Excel Navigation
Not applicable — Paperclip does not interact with Excel files directly.

## Escalation Triggers
Paperclip monitors infrastructure health, not business metrics:
- Agent heartbeat stale > 120 seconds → log warning
- Agent heartbeat missing > 300 seconds → mark inactive, log alert
- Event routing failure after 3 retries → log to `#escalations`
- Downstream service (sync-back, email-notifier) unreachable → alert

## Output Format
Paperclip logs use structlog JSON format:
```json
{"event": "ticket_created", "ticket_id": "PPC-0042", "type": "query", "department": "cac", "timestamp": "..."}
{"event": "heartbeat_updated", "agent": "cfo-agent", "department": "cac"}
{"event": "event_routed", "url": "http://sync-back:3006/process-approved", "context": "sync_back_approve"}
{"event": "event_route_failed", "url": "...", "max_retries": 3}
```

## Hard Rules
- Never write to `/data/mirror/` — read-only zone
- Never execute agent logic — Paperclip is routing/audit only
- Never skip event routing on approval — sync-back AND email-notifier must both be called
- Never expose PII in ticket payloads — use interaction_ids, not raw user data
- Never allow cross-department ticket creation — validate agent belongs to department
- Never bypass API key authentication on non-health endpoints
- Path traversal protection on all staging file operations

## Maintenance Procedures

### Adding a New Department
```
1. POST /departments with department config (name, slack_channel, hod_email, data_zone)
2. POST /departments/{name}/agents for each agent (orchestrator + specialists)
3. Create skills/{name}/ directory with SKILL.md files
4. Create Qdrant collections ({name}_docs, {name}_chat)
5. Create /data/staging/{name}/pending/, approved/, rejected/ directories
6. Add Docker service for department's orchestrator
7. Update config/departments.json
```

### Adding a New Agent to Existing Department
```
1. POST /departments/{dept}/agents with agent details
2. Agent starts sending heartbeats to POST /heartbeat
3. Verify agent appears in GET /heartbeats with "healthy" status
```

### Checking Service Health
```bash
# Quick health check
curl http://localhost:3100/health

# Check all agent heartbeats
curl -H "X-API-Key: $PAPERCLIP_API_KEY" http://localhost:3100/heartbeats

# Check recent tickets
curl -H "X-API-Key: $PAPERCLIP_API_KEY" "http://localhost:3100/tickets?limit=10"

# Check departments
curl -H "X-API-Key: $PAPERCLIP_API_KEY" http://localhost:3100/departments
```

### Troubleshooting

**Tickets not being created:**
1. Check cac-orchestrator logs: `docker logs cac-cac-orchestrator | grep paperclip`
2. Verify Paperclip is reachable: `curl http://paperclip:3100/health` (from inside Docker network)
3. Check Paperclip logs: `docker logs cac-paperclip | grep error`
4. cac-orchestrator falls back to stub IDs (PPC-STUB-XXXX) when Paperclip is down

**Heartbeats showing stale:**
1. Check agent container is running: `docker ps | grep cac-orchestrator`
2. Check agent logs for heartbeat errors: `docker logs cac-cac-orchestrator | grep heartbeat`
3. Verify DNS resolution: `docker exec cac-paperclip curl http://cac-orchestrator:3001/health`

**Approval webhooks not routing:**
1. Check Paperclip logs: `docker logs cac-paperclip | grep webhook`
2. Verify approval-ui is sending webhooks: `docker logs cac-approval-ui | grep paperclip`
3. Check downstream services: `curl http://sync-back:3006/health` and `curl http://email-notifier:3005/health`
4. Event router retries 3x with exponential backoff — check for "event_route_failed" in logs

**Database connection issues:**
1. Check Postgres: `docker exec cac-postgres pg_isready`
2. Verify tables exist: `docker exec cac-postgres psql -U cac_user -d cac_db -c "\dt paperclip_*"`
3. Re-run migration if needed: `docker exec -i cac-postgres psql -U cac_user -d cac_db < migrations/007_paperclip_tables.sql`

## Related Skills
- [[escalation-protocol]] — Escalation severity tiers and thresholds
- [[cfo-agent]] — CFO Agent persona (registered as cac-orchestrator)
- [[excel-navigation]] — Excel structure for staging proposals
- [[citation-format]] — How agents format citations in responses
