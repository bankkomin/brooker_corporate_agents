# Reality Check — Brooker Corporate AI Agents

**Date:** 2026-04-29
**Author:** Independent review (Claude Opus 4.6) against full codebase, PRD, and Phase 2 spec
**Purpose:** Honest assessment of what works, what's overclaimed, and what to ship first

---

## 1. What Actually Works Well

### Staging Pipeline (Mirror -> Stage -> Approve -> Sync)
The best-designed part of the system. Docker `:ro` enforcement on `/data/mirror/`, JSON manifests in `/data/staging/pending/`, human-in-the-loop approval via email deep-links, watchdog-triggered sync-back. This is exactly the right pattern for a system that touches financial spreadsheets. The "lethal trifecta" is not over-engineering — it is appropriate engineering.

### Basic RAG Q&A
Simple factual lookups from corporate documents work at ~60-70% reliability. "What does the ALCO Tracker say in cell E8?" or "What is the current LCR?" will return correct answers when the information is stated clearly in a single document chunk. The Qdrant + embedding + LangGraph pipeline is a proven pattern.

### Cross-Department Access Matrix
Config-driven via `departments.json`, enforced in application code with weighted retrieval (own=1.0, shared=0.7, cross=0.4). The wildcard pattern for CEO/Legal is now resolved from config. Good policy design.

### Template Approach for Departments
`services/_template-orchestrator/` + 12-step onboarding checklist is pragmatic. Will save real time after the first 2-3 departments stabilize the template.

### Data Safety Architecture
Zone-based data model, `:ro` Docker volumes, staging-only writes, JWT-authenticated approval, audit trail in Postgres. This is production-grade security design.

---

## 2. Where Claims Exceed Reality

### 2.1 "Self-Improving Agents" — Large Gap

**What the spec says:** Agents accumulate a "second brain" (soul.md/user.md/memory.md), a nightly reflection engine promotes lessons learned, and a self-improvement actuator proposes SKILL.md updates from feedback patterns.

**What actually happens:**
- Daily logs are appended (useful for audit, not self-improvement)
- Nightly cron asks Qwen 122B to analyze logs and produce JSON memory updates. With a local 122B model, this produces mostly noise — the model has no calibrated notion of "highly confident" in the context of corporate financial data
- Memory updates accumulate in `memory.md` and get loaded into every prompt. Over time, this becomes cruft that wastes context window without improving answer quality
- The pattern detector triggers on >=5 interactions with avg signal_strength < 0.5. Five data points is not statistically meaningful — one extra rejection flips the trigger
- The "approval-as-rating" mapping (approved=1.0, edited=variable, rejected=0.0) is a crude proxy. HODs approve bad proposals when busy and reject correct ones for non-quality reasons

**Honest label:** "Feedback logging with optional memory notes." Not self-improving agents.

**Recommendation:** Ship daily logs for audit. Defer reflection engine. Manual memory updates by the team are more reliable than LLM-generated ones.

### 2.2 "Proactive Heartbeat Agents" — Large Gap

**What the spec says:** Agents proactively check if trackers need updating, draft proposals, and post to Slack channels.

**What actually exists:** Two stub functions returning hardcoded strings:
```python
async def _gather_slack(channel: str) -> str:
    return f"(Slack #{channel} — stub: real implementation requires Slack API credentials)"
```

The dispatcher architecture (APScheduler + per-dept cron) is correct but the pipeline from context gathering to action is 0% functional. All departments have `heartbeat.enabled: false`.

**Recommendation:** Do not deploy. Leave disabled. Build only after core Q&A is solid and there is real user demand for proactive updates.

### 2.3 "Reliable Financial Reasoning" — Medium Gap

**What works:** Direct lookups, single-document summarization, extracting values from clearly stated text.

**What doesn't work reliably:**
- Multi-hop reasoning across documents ("Compare this quarter's LCR trend against the covenant threshold and tell me our headroom")
- Table-heavy analysis (512-token chunks shred Excel tables into meaningless fragments)
- Calculations (LLMs are unreliable at arithmetic even when prompted to show work)
- Trend analysis requiring temporal reasoning across multiple report versions

**Why:** RAG retrieves chunks, not coherent financial models. Qwen 122B is ~80% of GPT-4 quality on financial reasoning tasks. No chain-of-thought prompting in `synthesise.py`.

### 2.4 "Confidence Scoring" — Medium Gap

The `confidence_score` flowing through the pipeline is LLM self-reported. LLM self-confidence is notoriously uncalibrated. A Qwen 122B model saying "0.91 confidence" has never been calibrated against ground truth for this specific document corpus. The mapping (>=0.85 = High, >=0.60 = Medium) gives users false precision.

The 0.85 threshold for staging proposals is a reasonable starting guess but is fundamentally arbitrary. Expect 2-4 weeks of empirical tuning with real queries.

### 2.5 "Citation Accuracy" — Medium Gap

The system uses `[N]` references mapped to retrieved chunks, but the LLM has no mechanism to verify it is citing the correct chunk. It will frequently attribute information to the wrong source, especially when multiple chunks discuss similar topics.

In corporate finance, a wrong citation is worse than no citation — it erodes trust. There is no citation-grounding step that cross-checks the LLM's `[1]` against actual source `[1]`.

### 2.6 "Independent Validation" — Small-Medium Gap

The `validate_proposal` node makes a second LLM call with the same Qwen 122B model to "independently verify" the proposal. This is not independent — same model, same biases, same evidence. It catches formatting errors and obvious hallucinations but not systematic model blindspots.

The genuinely useful part is the history cross-check (comparing against recent proposals for the same cell). The LLM "validation" is partial security theater but still catches sloppy errors.

---

## 3. Architecture Overcomplexity

### Current Service Count: 16+

| Service | Verdict |
|---------|---------|
| gateway | Keep — API routing + auth |
| cac-orchestrator | Keep — core agent |
| slack-bot | Keep — user interface |
| rag-ingestion | Keep — document pipeline |
| sync-mirror | Keep — data freshness |
| sync-back | Keep — approved changes |
| approval-ui | Keep — human-in-the-loop |
| postgres + qdrant | Keep — data stores |
| email-notifier | Merge into approval-ui |
| paperclip | Cut — use Postgres tables for audit/tickets |
| wiki-compiler | Cut — rag-ingestion already handles vault |
| reflection-engine | Defer — ship logs only, manual memory |
| heartbeat | Defer — 0% functional, all disabled |
| openclaw | Defer — no actual code, no immediate need |
| 9 future dept orchestrators | Defer — build when needed, not upfront |

**Minimum viable stack:** 8 services (slack-bot, rag-ingestion, cac-orchestrator, approval-ui+email, sync-mirror, sync-back, postgres, qdrant) + vLLM.

### Read-Only Departments Don't Need Full LangGraph

8 of 12 departments are `capabilityTier: read_only`. These do not need LangGraph graphs with staging writers, validation nodes, and Excel navigators. They need: embed query, search Qdrant, format answer. A single configurable read-only orchestrator service could serve all 8 departments from one container with config-driven routing.

---

## 4. Local LLM Reality (Qwen 122B on DGX Spark)

### Hardware Constraints

- Qwen3.5-122B-A10B (MoE, ~10B active per token) at Q8: ~120GB model weights
- DGX Spark: 128GB unified memory
- After model + embedder: ~8GB remaining for all other services
- Practical concurrent queries: 2-3 at full context, 5-6 at shorter contexts
- Generation speed: ~20-50 tokens/second. A 2048-token response takes 40-100 seconds
- The PRD target "p95 < 30 seconds" is aggressive for anything beyond short answers

### Capability Comparison

| Capability | Qwen 122B | GPT-4 / Claude |
|-----------|-----------|----------------|
| JSON output reliability | ~80% | ~98% (native JSON mode) |
| Complex instruction following | ~80% | ~90-95% |
| Financial reasoning | Basic — single-hop | Strong — multi-hop |
| Error recovery | Hallucinates confidently | Asks clarifying questions |
| Calibrated confidence | No | Somewhat |
| Context window | 131K (slow at length) | 128K-1M (fast) |

The local LLM choice is justified by data residency requirements. Budget 2x the prompt engineering effort compared to a cloud API deployment.

---

## 5. What's Missing for Production

### Critical Gaps

1. **No evaluation framework.** No golden-answer test set, no automated accuracy benchmarks, no A/B testing. The `agent_performance` view is a feedback signal, not an evaluation framework. Without this, you cannot measure if the system is getting better or worse.

2. **No observability.** No Prometheus metrics, no OpenTelemetry tracing, no dashboards. For a 16-service distributed system, when something is slow or wrong, there is no tooling to diagnose why.

3. **No PII handling.** HR department is `live: true` with `sensitivityLevel: restricted`, but no PII detection, no data masking in logs, no access controls on Qdrant collections. Qdrant has no auth — any service on the Docker network can query any collection directly.

4. **No staleness disclaimer.** The 15-minute sync interval means answers could be based on stale data. The system presents answers without any freshness indicator.

5. **Wiring gap: `db_conn=None` in synthesise.py.** Knowledge gaps from LLM self-report phrases are never actually recorded to the database. The detection code exists but the database connection is not passed through.

6. **No chunking strategy for Excel files.** The 512/128 chunk size shreds table structures into meaningless fragments. The Excel schema JSON helps the navigator, but RAG retrieval of table data will be poor.

### What Will Break First in Production

1. **JSON parsing failures from Qwen 122B.** `validate_proposal.py` does `json.loads(raw)` with no retry (unlike `sdk_client.py` which has 3 retries). First malformed JSON response blocks the proposal with a confusing error.

2. **Memory pressure.** 11 Python containers + Postgres + Qdrant + MinIO + 2 vLLM instances in 8GB remaining memory. One memory leak brings everything down.

3. **User trust erosion.** Wrong citations, overconfident answers to questions the model cannot answer, hallucinated numeric values in staging proposals. The first few bad experiences will make the committee stop using it.

---

## 6. What to Actually Ship First

### Phase A: Core Value (4 weeks)

Ship CAC Q&A + staging proposals. Nothing else.

- slack-bot + rag-ingestion + cac-orchestrator + approval-ui (with email merged in)
- sync-mirror + sync-back
- postgres + qdrant + vLLM
- **Total: 8 services**

Success metric: CAC committee members ask 10+ questions per week and approve 2+ staging proposals per week.

### Phase B: Iterate on Quality (8 weeks)

Before adding departments, fix the core:

- Build a golden-answer evaluation set (50 questions with known correct answers)
- Tune RAG parameters (chunk size, top-K, min_relevance) against real queries
- Add citation grounding (verify LLM citations match actual retrieved chunks)
- Add chain-of-thought prompting to synthesise.py for complex queries
- Fix JSON reliability (add constrained decoding or retries to validate_proposal)
- Add observability (Prometheus + basic dashboard)
- Tune the confidence threshold with real approval data

### Phase C: Expand Departments (6 weeks)

Only after Phase B metrics are solid:

- Add Finance (write-capable, tests cross-dept read)
- Build a single read-only orchestrator service for HR, Risk, Legal, IT
- Add departments one at a time based on user demand, not a predetermined schedule

### Phase D: Advanced Features (when earned)

Only when base system is trusted:

- Daily log analysis (manual review, not LLM reflection)
- Memory updates (human-authored, not auto-promoted)
- Heartbeat proactive agents (if users request it)
- Self-improvement proposals (if there is enough approval data to be meaningful — likely 6+ months)

---

## 7. Summary Scorecard

| Area | Claim | Reality | Gap | Action |
|------|-------|---------|-----|--------|
| Core RAG Q&A | Reliable financial Q&A | Basic lookup works; analysis unreliable | Medium | Ship, iterate on quality |
| Excel Staging | Auto-proposes cell updates | ~30-40% correct; good as draft-for-review | Medium | Ship, manage expectations |
| Self-Improvement | Agents learn over time | Noise generator; not meaningfully learning | **Large** | Defer, ship logs only |
| Heartbeat | Proactive anticipation | 0% functional stubs | **Large** | Defer entirely |
| 11-Dept Expansion | 1.5 days each | 3-4 days initially; over-engineered for read-only | Medium | Single read-only service |
| Architecture | Justified microservices | ~50% premature or redundant | Medium | Cut to 8 services |
| Local LLM | Comparable to cloud | ~80% of GPT-4 quality; JSON reliability is gap | Medium | 2x prompt engineering |
| Confidence Scores | Calibrated quality signal | Uncalibrated LLM self-report | Medium | Add evaluation framework |
| Citations | Accurate source attribution | Wrong source ~20-30% | Medium | Add grounding step |

---

## Bottom Line

The project has a solid core (RAG + staging pipeline + approval gate) buried under layers of aspirational architecture. The data safety design is genuinely good — the lethal trifecta is the right pattern.

The self-improvement narrative is the biggest gap between marketing and reality. Rename it to what it is: "feedback logging with optional memory notes."

Strip to the core. Ship it. Iterate for 8 weeks. Earn the right to add complexity.
