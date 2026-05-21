# Agent Communication Flow

How user requests reach an agent and get answered. Captures the **actual implementation** as of 2026-05-07, including divergences from the PRD.

---

## 1. Entry points — two surfaces, one orchestrator contract

There are **two ways** for a user to talk to the agent system. Both end up calling the same orchestrator HTTP endpoint with the same payload shape.

```
                                          ┌──────────────────┐
  Slack @mention      ─►  slack-bot   ───►│                  │
  (#cac-committee,                         │  POST /query     │
   #hr-committee, ...)                     │                  │──►  dept-orchestrator
                                          │  {                │     (LangGraph runs here)
  Web / API call      ─►  gateway     ───►│    query,         │
  (POST /api/chat)                         │    user_id,       │
                                          │    channel,       │
                                          │    thread_ts      │
                                          │  }                │
                                          └──────────────────┘
```

### Slack entry point — `services/slack-bot/`
Listens to Slack Events API. Routes by **channel ID** (no LLM involved). The channel ID is the dept-routing key.

### Gateway entry point — `services/gateway/` (port 3000)
The website / external API entry. Comment in `chat.py:1`:
> "Replaces Slack as the entry point for queries."

`POST /api/chat` accepts a JWT (CAC-issued or Brooker SSO), checks `agent_access.can_query`, then proxies to the orchestrator with `channel="web"` and `thread_ts="web:{user_id}"`.

Other gateway routers (already wired): `proposals`, `escalations`, `analytics`, `uploads`, `skill_proposals`, `admin`, `memory`, `compliance`, `reports`, `cross_dept`, `venture_monitor`.

---

## 2. Two-tier routing

The user's request goes through **two routing decisions**: one structural (no AI), one semantic (LLM).

```
Tier 1 — STRUCTURAL ROUTING (no AI)
────────────────────────────────────
slack-bot or gateway picks the dept-orchestrator URL
based on channel_id (Slack) or JWT claim / request body (API).

  #cac-committee   → cac-orchestrator:3001
  #hr-committee    → hr-orchestrator:3001
  #risk-committee  → risk-orchestrator:3001
  ...


Tier 2 — SEMANTIC ROUTING (LLM)
────────────────────────────────
Inside the dept orchestrator, the LangGraph runs:

  classify_intent     ← LLM picks which specialists fire
  retrieve_context    ← RAG (dept Qdrant collections only)
  parallel fan-out    ← matched specialists run concurrently
  escalation_check
  excel_navigator     (write-tier depts only)
  staging_writer      (write-tier depts only, confidence ≥ 0.85)
  synthesise_response ← LLM merges specialist outputs
  create_paperclip_ticket
```

**Key insight:** specialists (`policy-agent`, `compensation-agent`, `liquidity-agent`, etc.) are **NOT separate services**. They are **nodes inside the dept orchestrator's LangGraph** — Python functions called by the graph. Only orchestrators expose HTTP.

---

## 3. Worked example — CHRO asks an HR question

CHRO posts in `#hr-committee`: *"What's our policy on long-service bonuses?"*

```
1. Slack event hits slack-bot
   event.channel = C07ABCDEFGH

2. slack-bot looks up channel ID in config/departments.json
   → matches hr.slackChannels.general (HR_CHANNEL_ID)
   → dept = "hr"

3. slack-bot POSTs to http://hr-orchestrator:3001/query
   { query, user_id=U..., channel=C07..., thread_ts=... }

4. hr-orchestrator's LangGraph:
   classify_intent     → ["policy", "compensation"]
   retrieve_context    → hr_docs + hr_knowledge + shared_policies
   fan-out:
     policy-agent       ✓ runs
     compensation-agent ✓ runs
     talent-agent       ✗ skipped
   escalation_check    → none
   staging_writer      → SKIPPED (HR is read_only tier)
   synthesise_response → merged answer with citations

5. hr-orchestrator returns JSON to slack-bot

6. slack-bot posts the reply as a thread reply in #hr-committee
```

**HR cannot create staging proposals** because `capabilityTier: "read_only"` (`config/departments.json:149`). The graph still runs, but the `staging_writer` node is disabled.

---

## 4. Dept isolation — why one orchestrator per dept

Each dept has its own service container. This is **load-bearing for confidentiality**.

| Dept | Container mounts | Qdrant collections | Cross-read |
|---|---|---|---|
| cac | `/data/mirror/alco/`, `/data/mirror/treasury/` | `cac_docs, cac_chat, cac_knowledge` | finance, risk, cio, ceo |
| hr | `/data/mirror/hr/` | `hr_docs, hr_chat, hr_knowledge` | **none** (siloed) |
| risk | `/data/mirror/risk/` | `risk_docs, risk_chat, risk_knowledge` | cac, cio, finance, legal |
| legal | `/data/mirror/legal/` | `legal_docs, legal_chat, legal_knowledge` | `*` (all) |

A monolithic orchestrator would need access to everything → blast-radius problem. Per-dept orchestrators mean even if one is compromised, it physically can't read other depts' data.

`crossReadAccess` controls **inbound** read access (who can read this dept's data). `[]` means siloed (HR). `["*"]` means everyone (Legal). `shared_policies` is always available to every dept.

---

## 5. State and conversation continuity

LangGraph uses `PostgresSaver` checkpointer with state key `(user_id, channel)`.

- Slack: same `channel_id` + same user → state continues across messages in the channel.
- Web: `channel="web"`, `thread_ts="web:{user_id}"` → continuous per-user conversation.

A follow-up question in the same Slack thread or web session resumes the same graph state — no need to re-explain context.

---

## 6. LLM provider — current state

**The PRD specifies 100% on-premise (Qwen3.5 122B + 9B embed via vLLM at `host.docker.internal`).**

**The code currently uses Google Gemini via the google-genai SDK** (`services/cac-orchestrator/src/tools/llm_client.py`):

```python
class LLMClient:
    def __init__(self, ..., model: str = "gemini-3.1-flash-lite-preview", api_key: str = "", ...):
        self._client = genai.Client(api_key=api_key) if api_key else genai.Client()
```

This is a **divergence from the PRD's data-residency principle** (PRD line 700: "Data residency: 100% on-premise"). Current implementation sends prompts to Google. Either:
- The PRD needs to be updated to reflect the chosen architecture, or
- The LLM client needs to be swapped back to vLLM/local Qwen, or
- A hybrid factory pattern needs to be introduced (provider chosen per-dept based on data sensitivity).

**Implication for confidential / restricted depts:** HR (`restricted`), Risk (`restricted`), Legal (`restricted`), CAC (`confidential`) data is currently being sent to a third-party LLM in production code path. This is a compliance question, not just a technical one.

### Making the provider switchable

`langchain-openai` and `google-genai` can both be hidden behind a factory. The orchestrator only calls `LLMClient.chat(messages, ...)`, so the provider can be swapped without touching graph logic:

```python
def make_llm_client(provider: str = "dgx"):
    if provider == "dgx":
        # vLLM via OpenAI-compatible endpoint
        return OpenAILLMClient(base_url="http://host.docker.internal:8000/v1", ...)
    if provider == "gemini":
        return GeminiLLMClient(api_key=os.getenv("GEMINI_API_KEY"), ...)
```

If a hybrid is desired, recommended guard: a security-auditor check that **fails the build** if `LLM_PROVIDER=gemini` is set in any container that mounts `/data/mirror/` or `/data/staging/`.

---

## 7. Known gaps for multi-dept scale-out

Two CAC-hardcoded spots in the gateway will break the moment a non-CAC dept goes live on the API:

### Gap 1 — single orchestrator URL
`services/gateway/src/chat.py:23`
```python
CAC_ORCHESTRATOR_URL = os.getenv("CAC_ORCHESTRATOR_URL", "http://localhost:3001")
```
Needs to become a per-dept lookup:
```python
ORCHESTRATOR_URLS = {
    "cac": os.getenv("CAC_ORCHESTRATOR_URL", "http://cac-orchestrator:3001"),
    "hr":  os.getenv("HR_ORCHESTRATOR_URL",  "http://hr-orchestrator:3001"),
    # ...
}
url = ORCHESTRATOR_URLS[claims.dept]   # or body.dept
```

### Gap 2 — Brooker middleware hardcodes dept="cac"
`services/gateway/src/main.py:134`
```python
access = await resolve_agent_permissions(
    pool, employee_id=None, email=claims.email, department_name="cac",
)
```
Should read the dept from the JWT claim (`claims.dept`) so a Brooker SSO user gets resolved against the right dept's `agent_access` rows.

slack-bot does **not** have this issue — it routes by channel ID, which is already dept-aware.

---

## 8. Service / port reference

| Service | Port | Role in the flow |
|---|---|---|
| `gateway` | 3000 | API entry — JWT auth, permission gate, proxy to dept orchestrator |
| `cac-orchestrator` | 3001 | LangGraph for CAC — only `live: true` orchestrator in Phase 1 |
| `slack-bot` | 3003 | Slack Events API listener — routes by channel ID |
| `rag-ingestion` | 3004 | Indexes docs, Slack messages, Obsidian vault into Qdrant |
| `hr-orchestrator` | 3001 (per-container) | Phase 2 — skeleton at `services/hr-orchestrator/` |
| `_template-orchestrator` | — | Copy this when scaffolding a new dept |
| `paperclip` | 3100 | Audit trail — every agent step gets a ticket |
| `approval-ui` | 4000 | HOD review dashboard (browser, opened from email link) |

---

## 9. References in code

- Gateway entry: `services/gateway/src/main.py`, `services/gateway/src/chat.py`
- Slack bot: `services/slack-bot/src/main.py`, `services/slack-bot/src/responder.py`
- CAC orchestrator graph: `services/cac-orchestrator/src/main.py`, `nodes/`, `agents/`
- LLM client (Gemini today): `services/cac-orchestrator/src/tools/llm_client.py`
- Dept config (channel IDs, agent topology, capability tiers): `config/departments.json`
- PRD source of truth (specifies on-premise — diverges from code): `PRD.md` §2, §8.1, §8.3
