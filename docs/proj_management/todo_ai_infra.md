# TODO — AI / LLM Infrastructure

vLLM deployment, model serving, embeddings, LLM connectivity, and prompt correctness.

---

## P0 — Critical

### [ ] Fix validate_proposal sending system-only message to LLM
- **Audit finding (AI-C2)** — may produce garbage output or refuse to generate
- `services/cac-orchestrator/src/nodes/validate_proposal.py:96`
- Entire validation prompt (including dynamic values) passed as single system message, no user message
- OpenAI-compatible API expects at least one `user` role message
- Every other LLM call in the codebase correctly uses `[system, user]` pairs
- **Fix:** Split prompt — static role description as system message, dynamic proposal data as user message

### [ ] Fix LLM client retry not covering transport errors and 5xx
- **Audit finding (AI-C1)** — transient 503 from nginx crashes queries
- `services/cac-orchestrator/src/tools/llm_client.py:22`
- Tenacity retry only catches `httpx.ConnectError` + `httpx.ReadTimeout`
- Misses: `httpx.WriteTimeout`, `httpx.PoolTimeout`, `httpx.RemoteProtocolError`, `httpx.HTTPStatusError` (5xx)
- A transient 503 during vLLM restart propagates as unhandled exception
- **Fix:** Use `retry_if_exception_type(httpx.TransportError)` to match embedder.py pattern; add 5xx handling

### [ ] Fix wiki-compiler ChatOpenAI missing timeout
- **Audit finding (AI-C3)** — ReadTimeout on 122B generation
- `services/wiki-compiler/src/compiler.py:39` — no `request_timeout` parameter
- Default 60s timeout; 122B model may need 120-180s for article compilation
- Failure is swallowed by fire-and-forget caller — wiki articles silently lost
- **Fix:** Add `timeout=180` and `max_retries=2` to `ChatOpenAI` constructor

### [ ] Deploy Qwen 3.5 122B on DGX Spark host
- Launch script: `infra/vllm/start-122b.sh`
- Serves on `http://localhost:8000/v1` (OpenAI-compatible API)
- **Blocking:** Without this, all LLM calls fail

### [ ] Deploy Qwen 3.5 9B embedding model on DGX Spark host
- Launch script: `infra/vllm/start-embed.sh`
- Serves on `http://localhost:8002/v1`
- **Blocking:** Without this, RAG ingestion produces zero vectors

---

## P1 — High

### [ ] Fix model name inconsistency across services
- **Audit finding (AI-H1)** — 100% failure at deployment if names don't match vLLM
- `services/cac-orchestrator/src/config.py:16` defaults to `"qwen-122b"`
- `services/wiki-compiler/src/config.py:9` defaults to `"qwen-3.5-122b"`
- `.env.example` uses `VLLM_LARGE_MODEL=qwen-large`
- All must match the exact `--served-model-name` in `infra/vllm/start-122b.sh`
- **Fix:** Standardise to one canonical name; verify with `GET http://localhost:8000/v1/models`

### [ ] Fix LLM client 60s timeout too short for 122B model
- **Audit finding (AI-H2)** — fires duplicate retries while original request runs
- `services/cac-orchestrator/src/tools/llm_client.py:14` — `timeout=60.0`
- 122B Q8 at ~20 tok/s for 2048 tokens = ~100s. Client times out at 60s, retries 3x
- Sends 3 duplicate requests to vLLM — can cause GPU OOM or queue backup
- **Fix:** Set `timeout=180.0` (or configurable via settings)

### [ ] Fix JSON parse fallback not logging raw LLM content
- **Audit finding (AI-H3)** — blind in production debugging
- `services/cac-orchestrator/src/agents/base.py:127-153`
- When LLM returns non-JSON, logs `agent_json_parse_failed` but not the raw content
- Returned confidence 0.5 prevents proposal pipeline but raw hallucination text still flows to synthesise
- **Fix:** Add `raw=raw[:500]` to the structlog call

### [ ] Remove embedding dimension 1536 fallback
- **Audit finding (AI-H5)** — silently creates broken Qdrant collections
- `services/rag-ingestion/src/main.py:49` — falls back to `dim = 1536` if vLLM unreachable
- Qwen 3.5 9B actual dimension: 4096 (not 1536)
- Collections created with wrong dimension; all subsequent upserts fail with dimension mismatch
- **Fix:** Fail fast at startup if embed endpoint is unreachable; remove 1536 fallback or replace with configurable `EMBEDDING_DIM` env var

### [ ] Fix wiki-compiler parameter naming confusion
- **Audit finding (AI-H4)** — maintenance trap
- `services/wiki-compiler/src/compiler.py:80` — `_build_system_prompt(self, event_type)` but receives `article_type`
- If called with raw `event.event_type` instead of mapped type, schema lookup misses silently
- **Fix:** Rename parameter to `article_type`

### [ ] Verify vLLM OpenAI-compatible endpoint responses
- Test `/v1/chat/completions` with a sample prompt (122B model)
- Test `/v1/embeddings` with a sample text (9B model)
- Record actual embedding dimension for Qdrant collection setup

### [ ] Confirm `host.docker.internal` resolution inside containers
- Add `extra_hosts: ["host.docker.internal:host-gateway"]` if needed
- Test: `docker exec <container> curl http://host.docker.internal:8000/v1/models`

---

## P2 — Medium

### [ ] Add `seed` parameter to classify_intent for determinism
- **Audit finding (AI-M1)** — non-deterministic routing possible
- `services/cac-orchestrator/src/nodes/classify_intent.py:35` — `temperature=0.0` but no `seed`
- vLLM temperature=0 can still be non-deterministic across batch sizes
- **Fix:** Add `"seed": 42` to the JSON payload

### [ ] Increase source excerpt in validate_proposal prompt
- **Audit finding (AI-M2)** — false hallucination flags
- `services/cac-orchestrator/src/nodes/validate_proposal.py:90` — truncates `context_text` to 500 chars
- Validator may flag content supported by non-truncated portion
- **Fix:** Increase to 1000-2000 characters

### [ ] Add retry/circuit-breaker to wiki-compiler LLM calls
- **Audit finding (AI-M3)** — failures silently dropped
- `ChatOpenAI` has default `max_retries=2` (from openai SDK) but no backoff or dead-letter
- Caller is fire-and-forget — failure is invisible
- **Fix:** Add explicit `max_retries=3` and consider dead-letter queue for failed compilations

### [ ] Fix rag-ingestion embedder_type defaulting to "mock"
- **Audit finding (AI-M4)** — local dev silently stores zero-vectors
- `services/rag-ingestion/src/config.py:12` — `embedder_type: str = "mock"`
- Docker Compose overrides to `vllm`, but local runs use mock silently
- **Fix:** Default to `"vllm"`, enable mock explicitly in test config only

### [ ] Fix conversation history deserialization from checkpointer
- **Audit finding (AI-M5)** — potential garbage in agent prompts
- `services/cac-orchestrator/src/agents/base.py:113` — `getattr(m, "type", "unknown")` fails if `m` is a dict (from PostgresSaver deserialization)
- **Fix:** Add `isinstance(m, dict)` check before `getattr`

### [ ] Verify wiki-compiler `extra_hosts` in dev compose
- **Audit finding (AI-M6)** — may not reach vLLM in dev mode
- `docker-compose.dev.yml` may override wiki-compiler entry without inheriting `extra_hosts`

### [ ] Evaluate LangGraph parallel fan-out vs linear chain
- Current: linear chain (classify -> one agent -> synthesise)
- PRD specifies: parallel fan-out (run multiple agents simultaneously)
- If upgrading, modify `graph.py` to use LangGraph `Send()` API
- **Note:** CFO agent's cross-domain synthesis depends on this — currently empty (see todo_services.md)

---
*Last updated: 2026-04-10*
