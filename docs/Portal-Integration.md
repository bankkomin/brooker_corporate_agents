# Portal Integration

How the Brooker employee portal (`brooker-internal-company` + `brooker-internal-company-interface`) connects to this corporate-agents system. Useful when working on either side of the boundary.

> **Audience:** anyone touching the gateway, the orchestrators, or the portal's `/paperclip-agent` page. Skim §1 for the mental model, then jump to the section that matches your change.

---

## 1. The portal is a fourth communication channel

The PRD originally listed three: Slack, Email, Approval UI, Obsidian. The portal is now a fourth and treats this corporate-agents system as a backend service.

```
Slack       ─┐
Email       ─┤
Approval UI ─┼──> brooker_corporate_agents (gateway → orchestrators)
Obsidian    ─┤
Portal      ─┘   ← new: brooker-internal-company-interface @ /paperclip-agent
```

Concretely, the portal:

- Lets users **chat with department orchestrators** through `/paperclip-agent` (currently only CAC is reachable; see §3).
- **Manages access** to those orchestrators per-employee or per-department, with the CEO getting auto-bypass.
- **Uploads files** (PDF/Word/Excel/PowerPoint/images/text) and stores them under the portal's local disk, with metadata in Postgres.
- **Records token usage** of every AI call (regular + Live realtime) so spend can be rolled up per user / per agent / per day.

The corporate-agents system mostly doesn't know about any of that — it just sees JWT-bearing HTTP requests at the gateway. Two integration points matter (§3).

---

## 2. Portal-side data model (in `brooker_employee` Postgres)

Tables that pertain to this system. All tables live in the **portal's** `brooker_employee` database, not the corporate-agents database — they're concerns of the portal's access layer.

| Table | Purpose |
|---|---|
| `paperclip_agent_access` | Platform-level access (whether `/paperclip-agent` route loads at all). Roles: owner / admin / member. CEO + system-admin auto-grant `owner`. |
| `paperclip_employee_agent_access` | Per-employee per-agent grants. `(employee_id, agent_slug)` unique. Jason can have rows for `legal`, `risk`, `cac`. |
| `paperclip_dept_agent_access` | Per-department per-agent grants. `(recipient_department_id, agent_slug)` unique. "Everyone in HR can use the HR agent." |
| `paperclip_files` | Uploaded files. Metadata in DB; bytes on disk under `${STORAGE_PATH}/paperclip-files/`. |
| `paperclip_agent_messages` | Local chat history (mirrors what's sent to the gateway). Each message carries a `metadata.agentSlug`. |
| `paperclip_agent_config` | Bot kill-switch + other key/value settings. |

`agent_slug` values match the keys in `config/departments.json`: `cac`, `risk`, `legal`, `hr`, `it`, `ceo`, `finance`, `ib`, `ic`, `cio`, `vcc`, `comms`.

### Effective-access rule

For a given employee, "which agents can they chat with?":

1. If `employees.role = "ceo"` → **every available agent**, no grants needed.
2. Otherwise → union of `paperclip_employee_agent_access` rows + `paperclip_dept_agent_access` rows for the employee's department.
3. The platform-level `admin` role does **not** auto-bypass per-agent grants. Sysadmins manage the grant system but only see agents they've been explicitly granted (or that their dept has).

Implemented in `brooker-internal-company/src/modules/paperclip/paperclip.service.ts` — `listAgentsForEmployee(employeeId)`.

---

## 3. Two integration gaps you should know about

These are the parts that require *your* side (the corporate-agents system) to change, not the portal.

### 3.1 Gateway only routes to CAC

`services/gateway/src/chat.py` line 23 hardcodes:

```python
CAC_ORCHESTRATOR_URL = os.getenv("CAC_ORCHESTRATOR_URL", "http://localhost:3001")
```

Every `/api/chat` request — regardless of which department it's "for" — goes to that single URL.

**The portal already passes the target agent slug** in the chat body:

```jsonc
POST /api/chat
{
  "message": "What's our policy on annual leave?",
  "thread_id": "...",
  "agent_slug": "hr"      // ← portal sends this; gateway currently ignores it
}
```

The portal is forward-compatible. To make per-agent chat actually work end-to-end, update the gateway to:

1. Read `agent_slug` from the request body (default to `"cac"` for backward compat).
2. Look up the orchestrator URL by slug from a config table or env vars (`CAC_ORCHESTRATOR_URL`, `HR_ORCHESTRATOR_URL`, `RISK_ORCHESTRATOR_URL`, etc.).
3. Forward the request to the right orchestrator.
4. Update `agent_permissions` checks if you want per-orchestrator scope checks separate from the portal's grant check.

**Until that's done**: portal users see the right agent name in the UI selector, but the response always comes from CAC. Acceptable for one-orchestrator deployments; misleading for multi-orchestrator.

### 3.2 Files uploaded via portal aren't ingested into RAG

The portal stores uploads at `${STORAGE_PATH}/paperclip-files/<storedName>` and serves them via `GET /api/paperclip/files/:id` (auth-gated, JWT-bearing). The portal's `paperclip_agent_messages.metadata.files` array carries `{ id, name, mimetype, size }` for files attached to each chat turn.

**The orchestrator currently doesn't fetch them.** When a user attaches a file and asks a question, the chat call to the gateway has the file *referenced* in metadata but the agent has no way to read the contents.

To wire the agent up to read attached files:

1. Extend the chat request body to include `files: [{ id, name, mimetype, size }]`.
2. In the orchestrator's pre-retrieval step, for each attached file:
   - Fetch from `<portal>/api/paperclip/files/<id>` with a service-to-service token (TBD — needs a portal-side route + key, or pass the user's JWT through).
   - Run it through the same chunker as `rag-ingestion` (PDF/Word/Excel/PPTX/text) or rasterize images for vision models.
   - Inject the chunks into the LLM context for that turn.
3. Optionally, push the chunks to a per-user Qdrant collection so they're retrievable on follow-up questions.

The portal allow-list is a **superset** of what `rag-ingestion` supports — portal accepts images (jpg/png/gif/webp/svg) which the current chunker doesn't. Either expand the chunker to handle images via vision, or skip them when ingesting.

---

## 4. Things the portal handles, so you don't have to

Stay out of these — the portal owns them:

| Concern | Where it lives |
|---|---|
| **Authentication** of the end user (JWT issue + refresh) | Portal's `auth.routes.ts`. The gateway just validates the JWT it's given. |
| **Per-agent access checks** | Portal enforces `canEmployeeAccessAgent` before forwarding chat requests. The gateway can re-check via `agent_access` rows but isn't required to. |
| **File storage + serving** | Portal's local disk + `GET /api/paperclip/files/:id`. The corporate-agents system never sees the bytes unless §3.2 is wired. |
| **Token usage / cost tracking** | Portal records every AI call into `ai_usage`. The corporate-agents orchestrators *also* emit metrics (LangSmith or equivalent), but the portal's table is the customer-facing one for "how much have we spent on AI this month". |
| **Recap emails / scheduled notifications** | Portal-side via MS Graph. Corporate-agents email-notifier handles HOD escalations only. |

---

## 5. Quick-reference: portal endpoints related to this system

| Endpoint | Purpose | Who can call |
|---|---|---|
| `GET /api/paperclip/access` | Does this user see paperclip at all? | Any authenticated employee |
| `GET /api/paperclip/agents` | Catalog of all agents (from `config/departments.json`) | Any platform-access user |
| `GET /api/paperclip/my-agents` | Agents this user can chat with | Any platform-access user |
| `POST /api/paperclip/chat` | Forward a message + optional `agent_slug` to the gateway | Caller must have per-agent grant |
| `POST /api/paperclip/upload` | Upload a file (50 MB max) | Any platform-access user |
| `GET /api/paperclip/files/:id` | Stream/preview a file | Any platform-access user (refine if needed) |
| `POST /api/paperclip/employee-grants` | Grant Jason → legal/risk/cac | CEO / system admin / platform owner |
| `POST /api/paperclip/department-grants` | Grant whole department → agent(s) | CEO / system admin / platform owner |

The portal calls the corporate-agents gateway's `/api/chat`, `/api/proposals*`, `/api/escalations`, `/api/analytics/summary`, and `/api/auth/validate` — see `paperclip.service.ts` `gatewayFetch` for the full list. Anything outside those isn't touched by the portal.

---

## 6. Files allowed by the portal upload endpoint

Allow-list in `paperclip.service.ts` `ALLOWED_FILE_EXTS`:

```
pdf · docx · doc · xlsx · xls · csv · pptx · ppt
txt · md · json
jpg · jpeg · png · gif · webp · svg
```

50 MB cap per file, configurable.

How the portal previews each:

| Type | Preview |
|---|---|
| PDF | iframe (browser native viewer) |
| Image (jpg/png/gif/webp/svg) | `<img>` |
| text/json/markdown | iframe rendered as text |
| Office docs (xlsx/docx/pptx/csv/etc.) | "Download" card — no inline preview without server-side conversion |

If you add a LibreOffice-based PDF conversion service, the portal can switch the office-doc fallback to render a converted PDF in iframe. That's a portal-side change once you provide a conversion endpoint.

---

## 7. When in doubt

- If the user is asking "why don't I see HR agent's response when I select HR?" → §3.1.
- If the user is asking "why doesn't the agent see my uploaded PDF?" → §3.2.
- If the user is asking "I'm CEO but only see 3 agents" → check `employees.role` value and read §2 effective-access rule.
- If you're considering writing a new orchestrator → make sure `config/departments.json` has the right slug + `agentTopology.orchestrator` field, and add an env var like `<DEPT>_ORCHESTRATOR_URL` to the gateway.
