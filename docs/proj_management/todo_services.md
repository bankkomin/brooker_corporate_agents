# TODO — Services

Stubs, TODOs, wiring gaps, inter-service connection bugs, and missing implementations.

---

## P0 — Critical

### [ ] Fix slack-bot `channel_id` vs orchestrator `channel` field mismatch
- **Audit finding (API-2)** — silent data loss on every query
- `services/slack-bot/src/models.py:40` sends `channel_id` field
- `services/cac-orchestrator/src/models.py:25` expects `channel` field
- Result: `channel` is always empty string in orchestrator state; `notify_escalation` sends blank channel
- **Fix:** Rename `channel_id` to `channel` in slack-bot's `QueryRequest` model, or add `alias="channel_id"` on orchestrator side

### [ ] Fix paperclip → email-notifier `/notify/confirmed` payload mismatch
- **Audit finding (API-3)** — always returns 422
- `services/paperclip/src/services/event_router.py:184` sends `{"proposal_id": ..., "event": decision, "reviewer": reviewer}`
- `services/email-notifier/src/models.py:34` expects `{"proposal_id": ..., "decision": ..., "dept": ...}`
- Field `event` should be `decision`; `dept` is missing entirely; `reviewer` is not expected
- **Fix:** Update event_router.py payload to match `ConfirmedNotification` model

### [ ] Fix paperclip → slack-bot `/post-escalation` — endpoint doesn't exist
- **Audit finding (API-4)** — always returns 404
- `services/paperclip/src/services/event_router.py:197-201` POSTs to `http://slack-bot:3003/post-escalation`
- slack-bot only exposes `/slack/events` and `/health`
- **Fix (option A):** Add `/post-escalation` endpoint to slack-bot that posts to #escalations channel
- **Fix (option B):** Have paperclip post escalations directly via Slack API

### [ ] Fix paperclip → email-notifier `/notify/proposal` payload missing required fields
- **Audit finding (API-5)** — always returns 422
- `services/paperclip/src/services/event_router.py:216-219` sends only `{"proposal_id": ..., "department": ...}`
- `services/email-notifier/src/models.py:17` requires `agent_name`, `file`, `tab`, `cell`, `new_value`, `confidence`, `dept`
- **Fix:** Populate all required fields from the proposal manifest before sending

### [ ] Fix `cfo_agent` missing from graph conditional edge routing map
- **Audit finding (LG-1)** — runtime ValueError for any CFO query
- `services/cac-orchestrator/src/graph.py:172-179` — `"cfo_agent"` not in the routing dict
- `_route_to_agent` returns `"cfo_agent"` for cfo intent but LangGraph can't resolve it
- **Fix:** Add `"cfo_agent": "cfo_agent"` to the conditional edges map

---

## P1 — High

### [ ] Fix gateway missing `DATABASE_URL` in docker-compose.yml
- **Audit finding (API-7)** — all API routes crash with AttributeError
- `services/gateway/src/main.py:24` reads `os.getenv("DATABASE_URL")` — never set in docker-compose
- `db_pool` is never created; any request to `/api/proposals`, `/api/escalations`, `/api/analytics` crashes
- **Fix:** Add `DATABASE_URL=postgresql://...` to gateway service environment in docker-compose.yml

### [ ] Fix paperclip staging file layout mismatch
- **Audit finding (API-9)** — rejected proposals never moved
- `services/paperclip/src/services/event_router.py:109-125` looks for `pending/{proposal_id}.json` (flat file)
- `staging_writer.py` creates `pending/{proposal_id}/manifest.json` (directory layout)
- `os.path.exists(src)` always False — rejected proposals stay in `pending/` forever
- **Fix:** Update `move_staging_file()` to look for `pending/{id}/manifest.json`

### [ ] Fix orchestrator `notify_escalation` missing `dept` field
- **Audit finding (API-6)** — always defaults to "cac"
- `services/cac-orchestrator/src/nodes/notify_escalation.py:14-22` — payload missing `dept`
- email-notifier defaults to `"cac"` — wrong for multi-department queries
- **Fix:** Add `dept` from graph state to escalation payload

### [ ] Fix graph build failing when `llm_client` or `skills_loader` is None
- **Audit finding (LG-2)** — conditional edge destinations reference unregistered nodes
- `services/cac-orchestrator/src/graph.py:90-99` — agents dict empty when either arg is None
- But conditional edge map still references all agent node names — LangGraph raises on compile
- **Fix:** Guard the conditional edge map to only include registered agent nodes

### [ ] Fix CFO agent reading specialist output keys that are never written
- **Audit finding (LG-3)** — CFO synthesis always empty
- `services/cac-orchestrator/src/agents/cfo.py:12-17` reads `liquidity_output`, `capital_output`, etc.
- No agent ever writes these keys — `BaseAgent._parse_response` writes `agent_response`, not `{name}_output`
- **Fix:** Either have each specialist agent write to `{name}_output` in state, or have CFO read from the actual state keys

### [ ] Fix `validate_proposal` reading wrong state key for tab
- **Audit finding (LG-5 + LG-8)** — history cross-check always queries empty tab
- `services/cac-orchestrator/src/nodes/validate_proposal.py:66-68` reads `state.get("tab")`
- Correct key is `state.get("proposed_tab")` (declared in state.py:61, written by agents)
- **Fix:** Change `state.get("tab")` to `state.get("proposed_tab")`

### [ ] Fix `escalation_check` unscoped number extraction
- **Audit finding (LG-6)** — false triggers on dates, page refs, IDs
- `services/cac-orchestrator/src/nodes/escalation_check.py:46-63`
- `_extract_numbers` returns every decimal in the response (year 2026, citation [1], cell E8)
- Keyword proximity check only confirms keyword exists somewhere, not near the number
- **Fix:** Require keyword and number to appear within N characters of each other, or use structured agent output

### [ ] Wire `paperclip_ticket.py` to real Paperclip service
- **Status:** [x] Done (wired in previous session)
- `services/cac-orchestrator/src/nodes/paperclip_ticket.py` now POSTs to `http://paperclip:3100/tickets`

### [ ] Implement Paperclip worker manager (OpenClaw)
- `services/paperclip/src/services/worker_manager.py` is a stub
- Needs: Claude API key, task serialisation, result callback handling

### [ ] Fix Paperclip department extraction TODO
- **Status:** [x] Done (fixed in previous session)
- `services/paperclip/src/services/event_router.py` now reads from departments.json

---

## P2 — Medium

### [ ] Fix `paperclip_ticket_id` always None in staging manifest
- **Audit finding (LG-7)** — graph ordering issue
- `staging_writer` runs before `paperclip_ticket` in the graph
- `staging_writer.py:68` reads `state.get("paperclip_ticket_id")` — always None at that point
- **Fix:** Either run `paperclip_ticket` before `staging_writer`, or add a post-write update step

### [ ] Fix staging_writer counter resetting on restart
- **Audit finding (LG-8)** — duplicate `chg_XXXX` IDs cause DB INSERT failures
- `services/cac-orchestrator/src/nodes/staging_writer.py:17` — `itertools.count(1)` resets on restart
- **Fix:** Generate ID from DB sequence or UUID

### [ ] Fix excel_navigator ignoring `proposed_tab` in schema lookup
- **Audit finding (LG-9)** — first tab with matching row number wins regardless of intent
- `services/cac-orchestrator/src/nodes/excel_navigator.py:47-57`
- Should filter by `proposed_tab` before iterating rows
- **Fix:** Add `if tab["name"] == state.get("proposed_tab")` filter

### [ ] Fix `answer` vs `response` field name mismatch
- **Audit finding (LG-10)** — state uses `answer`, CLAUDE.md spec says `response`
- `services/cac-orchestrator/src/nodes/synthesise.py:91` writes `{"answer": ...}`
- API layer must read `state["answer"]`, not `state["response"]`
- **Fix:** Standardise to one name across state.py, synthesise.py, and main.py

### [ ] Fix gateway proposals.py TOCTOU race in approve flow
- **Audit finding (API-10)** — dept check after UPDATE leaves inconsistent state
- `services/gateway/src/proposals.py:151` — `check_dept_access` called after the UPDATE
- If AuthError fires, proposal is already approved in DB but no decision record is written
- **Fix:** Move dept access check before the UPDATE

### [ ] Fix paperclip `move_staging_file` blocking I/O
- **Audit finding (API-11)** — `shutil.move()` blocks event loop
- `services/paperclip/src/services/event_router.py:125`
- **Fix:** Wrap in `asyncio.to_thread()` or `run_in_executor()`

### [ ] Fix sync-back default DATABASE_URL pointing to wrong database
- **Audit finding (API-13)** — defaults to `brooker_agent`, all others use `corporate_agents`
- `services/sync-back/src/config.py:4`
- **Fix:** Change default to match other services

### [ ] Fix paperclip STAGING_DIR env var name mismatch
- **Audit finding (API-15)** — reads `STAGING_DIR`, docker-compose sets `STAGING_PATH`
- `services/paperclip/src/services/event_router.py:17`
- Default `/data/staging` happens to be correct, but naming inconsistency is fragile
- **Fix:** Standardise env var name across all services

### [ ] Add `old_value` to graph state and agent outputs
- **Audit finding (LG-4)** — manifest always records `old_value: null`, approvers see no diff
- No agent or node ever writes `old_value` to state
- `validate_proposal` defaults to `"(empty)"`, staging_writer writes `null`
- **Fix:** Have `excel_navigator` read current cell value from schema/mirror and write to state

### [ ] Wire CFO agent into orchestrator graph
- **Status:** [x] Done (created in previous session)
- `services/cac-orchestrator/src/agents/cfo.py` created, added to graph.py
- **Note:** Still needs conditional edge fix (see P0 above) and specialist output key fix (see P1)

### [ ] Verify HR orchestrator integration
- Stage 8 marks HR department as complete
- Verify: Are HR agents inside `cac-orchestrator` or a separate service?

### [ ] Add health endpoint to approval-ui
- **Status:** [x] Already exists at `src/app/api/health/route.ts`

### [ ] Review slack-bot orchestrator stub mode
- Verify `orchestrator_enabled` defaults to `true` in production `.env`
- If still `false`, @mentions return canned responses instead of real queries

### [ ] Ensure email-notifier SMTP fallback is documented
- **Status:** [x] Done (startup warning added in previous session)

---
*Last updated: 2026-04-10*
