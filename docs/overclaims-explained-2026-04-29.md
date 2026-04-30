# Why These Features Are Overclaimed — Detailed Technical Explanation

**Date:** 2026-04-29
**Context:** This document explains, with code references and reasoning, why specific features in the Brooker Corporate AI Agent system are overclaimed relative to what they can actually deliver. Written for an audience that wants to understand the "why" behind each gap.

---

## 1. "Self-Improving Agents" — The Biggest Overclaim

### What the system claims to do

The Phase 2 spec (section 4.4-4.7) describes agents that:
- Accumulate a "second brain" through a memory triad (soul.md / user.md / memory.md)
- Reflect nightly on their interactions and learn from mistakes
- Automatically propose improvements to their own SKILL.md behavior files
- Get smarter over time through a feedback loop based on HOD approval signals

This is inspired by two YouTube videos: Cole Medin's "second brain" and Luuk Alleman's "self-improving agent" patterns.

### Why it won't work as described

#### Problem 1: The LLM cannot reliably "reflect"

Look at `services/reflection-engine/src/sdk_client.py` lines 11-50. The reflection prompt asks Qwen 122B to:

```
Analyze yesterday's interactions and approval decisions, then determine what should be updated
in the agent's persistent memory.
...
Rules:
- Only promote facts you are highly confident about
```

**Why this fails:** The instruction "only promote facts you are highly confident about" assumes the model has a calibrated internal measure of confidence. It does not. LLMs do not know what they know. When you ask Qwen 122B to be "conservative," it interprets this instruction probabilistically — sometimes it produces empty arrays (too conservative), sometimes it promotes trivial observations like "User U001 asked about LCR" (not useful), and sometimes it hallucinates patterns that don't exist (dangerous).

The 3-retry JSON parsing loop (lines 80-100) exists because Qwen 122B fails to produce valid JSON ~20% of the time. Each retry is an independent roll of the dice — there is no mechanism for the model to learn from the previous failed attempt within the same call. The fallback (line 100) returns empty arrays, meaning on ~20% of nights the reflection engine produces nothing at all.

**Real-world comparison:** GPT-4 and Claude have better instruction-following (~90-95% vs ~80% for Qwen 122B). Even with GPT-4, reflection-style prompts produce noisy output that requires human curation. With Qwen 122B, the noise-to-signal ratio is significantly worse.

#### Problem 2: Memory accumulates cruft, not wisdom

The `promoter.py` writes LLM-generated content to `memory.md` and `user.md`, which then get loaded into EVERY future prompt via `load_memory_node()` in `services/shared/load_memory.py`:

```python
parts = []
for fname in ("soul.md", "user.md", "memory.md"):
    f = base / fname
    if f.is_file():
        content = f.read_text(encoding="utf-8").strip()
        if content:
            parts.append(content)
return {"agent_memory": "\n\n---\n\n".join(parts)}
```

After 30 nights of reflection, `memory.md` might contain:

```markdown
## Lessons
- LCR queries are commonly asked (night 1)
- User U001 prefers percentage format (night 3)
- NSFR data should include both consolidated and subsidiary (night 5)
- The covenant threshold is 100% not 110% (night 8 — THIS COULD BE WRONG)
- Consider checking BG weekly report for updated facility data (night 12)
- Capital ratio formatting should use 2 decimal places (night 15)
... (30+ entries)
```

This consumes ~500-2000 tokens of context window on EVERY query. The model must read through accumulated notes, most of which are irrelevant to the current question. Worse, if night 8's "lesson" is wrong (the model hallucinated that the covenant threshold is 100% when it's actually 110%), this wrong fact gets loaded into every future prompt and the agent systematically returns incorrect covenant analysis.

**There is no correction mechanism.** If a bad fact enters memory.md, it stays there until a human manually edits the file. The archive-before-overwrite in `promoter.py` (lines 42-54) only keeps historical versions — it does not detect or roll back bad updates.

**What actually works in industry:** Manual prompt engineering by humans who understand the domain. A financial analyst spending 30 minutes writing a `soul.md` with domain rules will produce better results than 6 months of automated reflection.

#### Problem 3: The feedback signal is too weak

The "approval-as-rating" system maps HOD actions to signal_strength:

```sql
-- From migrations/010_phase2_framework.sql, agent_performance view
CASE ad.action
  WHEN 'approved' THEN 1.0
  WHEN 'edited' THEN 0.5 + 0.5 * (1 - ABS(proposed - edited) / MAX(ABS(proposed), 1))
  WHEN 'rejected' THEN 0.0
END AS signal_strength
```

**Why this is not a reliable quality signal:**

1. **Approval does not mean correct.** A busy HOD might approve a proposal without carefully checking it. The agent gets signal_strength=1.0 for a potentially wrong answer. In corporate committees, rubber-stamping is common when the volume of proposals is high.

2. **Rejection does not mean wrong.** A HOD might reject because they want to update the value themselves, because they are waiting for a different data source, or because of politics. The agent gets signal_strength=0.0 for a potentially correct proposal.

3. **Editing distance is meaningless for non-numeric changes.** The formula `ABS(proposed_value::numeric - edited_value::numeric)` only works when both values are numbers. If the agent proposes "3.15" and the HOD edits to "See Q3 report," the view now returns 0.5 (the safe fallback) — but this edit represents a fundamentally wrong proposal, not a moderate one.

4. **5 data points over 7 days is statistical noise.** The pattern detector (`pattern_detector.py` lines 29-46) triggers when `COUNT(*) >= 5 AND AVG(signal_strength) < 0.5`. Consider this scenario:

   | Day | Proposal | HOD Action | Signal |
   |-----|----------|-----------|--------|
   | Mon | LCR=118.5 | Approved | 1.0 |
   | Tue | NSFR=104.2 | Edited to 104.8 | 0.97 |
   | Wed | Capital=15.8 | Rejected (wants to wait) | 0.0 |
   | Thu | Funding=2.1 | Rejected (political) | 0.0 |
   | Fri | Covenant=95% | Rejected (wrong source) | 0.0 |

   Average signal: 0.39. The detector triggers — "this agent needs improvement." But 2 of 3 rejections had nothing to do with agent quality. The system would propose a SKILL.md change based on noise.

#### Problem 4: "Self-improving" implies autonomous adaptation — this is human-in-the-loop with extra steps

The actual flow is:
1. Reflection engine suggests memory.md updates (noisy, ~20% failure rate)
2. Reflection engine suggests skill proposals (based on weak signal, rarely triggered)
3. Skill proposals go to the approval-ui for HOD review
4. HOD must manually approve/reject the proposed SKILL.md change
5. If approved, OpenClaw commits the change as a PR

This is not "self-improving." This is "AI suggests changes that humans must review and approve." That is a reasonable feature, but calling it self-improving implies the agent autonomously gets smarter. In reality, the agent produces suggestions of varying quality that a human must curate. The agent itself has no mechanism to verify whether its suggestions improved performance.

**Honest label:** "Feedback logging with AI-suggested prompt updates (human-gated)."

---

## 2. "Confidence Scoring" — Sounds Precise, Means Nothing

### What the system claims

The CAC orchestrator assigns a confidence score to every response and proposal. SKILL.md files reference this score. The staging pipeline uses a 0.85 threshold to gate proposals.

### Why it's overclaimed

Look at `synthesise.py` lines 31-37:

```python
def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "High"
    elif score >= 0.60:
        return "Medium"
    return "Low"
```

And `graph.py` line 42:
```python
async def _general_handler(state: dict) -> dict:
    return {
        "confidence_score": 0.5,  # hardcoded
    }
```

**The confidence score comes from the LLM itself.** When Qwen 122B says "confidence: 0.91," this is the model outputting a token that represents a number. It is not a calibrated probability. The model has never been tested against a ground-truth dataset of financial questions where we know the correct answers.

**What "calibrated confidence" would mean:** If the model says 0.90 confidence, it should be correct ~90% of the time. If it says 0.60, it should be correct ~60% of the time. LLMs — especially open-source ones — are notoriously poorly calibrated. Research papers consistently show that LLM self-reported confidence does not correlate well with actual accuracy. A Qwen 122B model saying 0.91 on a financial question and 0.91 on a trivia question will have very different actual accuracy rates.

**The 0.85 threshold is arbitrary.** It was chosen because it sounds reasonable, not because anyone tested what percentage of proposals above 0.85 are actually correct. In practice:
- If too many bad proposals pass 0.85: the HOD loses trust and starts rejecting everything
- If too many good proposals fail 0.85: the agent seems useless because it never proposes anything
- The "right" threshold depends on the model, the domain, and the specific Excel tracker — it requires empirical tuning that has not been done

**What would actually work:** Instead of self-reported confidence, use retrieval-based heuristics: number of source chunks retrieved, similarity score of top chunk, whether the extracted value appears verbatim in a source. These are measurable, reproducible signals. LLM self-confidence is not.

---

## 3. "Independent Validation" — Same Model Checking Itself

### What the system claims

`validate_proposal.py` provides "independent LLM review" — a second LLM call that verifies the proposal before it goes to staging.

### Why it's partially theater

Look at `validate_proposal.py` lines 96-105:

```python
raw = await llm_client.chat(
    [
        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ],
    temperature=0.0,
    max_tokens=500,
)
result = json.loads(raw)
```

**This is the same Qwen 122B model** checking its own output. The `llm_client` is the same vLLM instance. Setting `temperature=0.0` makes it deterministic but does not make it a different perspective.

**Why same-model validation has limited value:**
- If the model has a systematic bias (e.g., it consistently misreads a particular Excel column), the validation call will have the same bias
- If the model hallucinates a value, it will also hallucinate a justification for that value when asked to validate
- The model's "validation" is essentially: "does this JSON look reasonable?" — it can catch formatting errors but not semantic errors

**What actually provides independent validation:**
- A different model (e.g., a smaller Qwen 7B as a cheap cross-check, or a rule-based validator)
- Database lookups (compare against historical values for the same cell — this IS implemented in lines 66-84 and is the genuinely useful part)
- Schema validation (check that the proposed value matches the expected type/range for that cell — partially implemented via Excel schema)

**The history cross-check (lines 66-84) is the real value.** It compares against the last 3 proposals for the same cell. This catches: proposals that contradict recently approved values, proposals for the same cell by different agents, and value drift over time. This is deterministic, reproducible, and genuinely useful. The LLM validation call on top of it adds marginal value at significant latency cost (~5-15 seconds per proposal).

---

## 4. "Citation Accuracy" — No Grounding Verification

### What the system claims

Agents cite their sources using `[N]` references. The synthesise prompt (lines 18-28) instructs:

```
Rules:
- Include source citations in [N] format referencing the provided sources
```

### Why citations are unreliable

The RAG pipeline retrieves chunks from Qdrant, numbers them `[1]`, `[2]`, etc., and passes them to the LLM. The LLM generates an answer and sprinkles `[1]`, `[2]` references throughout.

**The problem:** The LLM is guessing which source supports which claim. It does not verify. Common failure modes:

1. **Source shuffling:** The model writes "According to [1], the LCR is 118.5%" but the LCR figure actually came from source [3]. The model associated [1] because it appeared first in the context window.

2. **Citation to irrelevant sources:** The model cites [2] for a claim, but [2] is about a completely different topic that happened to be retrieved because of keyword overlap.

3. **Fabricated precision:** The model writes "Per the Q3 ALCO report [1], the covenant headroom is 18.5 basis points" but [1] contains no such specific number — the model interpolated from partial information and attributed its calculation to the source.

**In corporate finance, a wrong citation is worse than no citation.** If an HOD clicks through to verify "[1]" and finds it doesn't support the claim, they lose trust in the entire system. This happens ~20-30% of the time with current RAG systems, regardless of the LLM used.

**What would fix this:**
- Post-generation citation grounding: after the LLM generates an answer, check each `[N]` reference against the actual chunk and flag mismatches
- Extractive citation: instead of letting the LLM choose citations, highlight the exact extracted text spans from each source
- These are not implemented in the current system

---

## 5. "Proactive Heartbeat Agents" — Architecture Without Implementation

### What the system claims

Spec section 4.8 describes agents that proactively:
- Check if trackers need updating
- Gather context from Slack and SharePoint
- Draft proposals before anyone asks
- Post anticipatory messages to Slack channels

### Why this is premature

Look at `services/heartbeat/src/context_gatherer.py` lines 32-45:

```python
async def _gather_slack(channel: str) -> str:
    log.info("Slack context gather stub for #%s", channel)
    return f"(Slack #{channel} — stub: real implementation requires Slack API credentials)"

async def _gather_sharepoint(path: str) -> str:
    log.info("SharePoint context gather stub for %s", path)
    return f"(SharePoint {path} — stub: real implementation requires SharePoint API credentials)"
```

Both context sources are stubs. The entire value proposition of proactive agents is: "I noticed something changed, so I'm suggesting an update." With stub data sources, the agent has nothing to notice.

And `services/heartbeat/src/orchestrator_client.py` lines 8-19 hardcode port mappings:

```python
DEPT_PORTS = {
    "cac": 3001,
    "hr": 3002,
    "finance": 3010,
    ...
}
```

This will immediately drift from the actual port assignments in docker-compose.yml. It should read from `departments.json` or use Docker DNS.

**Even if fully implemented, proactive agents have a fundamental UX problem:** unsolicited messages in Slack channels create noise. Unless the signal-to-noise ratio is very high (>80% useful messages), users will mute the bot. The system has no mechanism to measure or improve this ratio — there is no feedback loop on heartbeat outputs.

**Why it was built too early:** The core Q&A is not yet validated with real users. Building a proactive layer on top of an unvalidated reactive layer means you're automating something you don't know works yet.

---

## 6. "11 Departments in 1.5 Days Each" — Over-Engineered for Read-Only

### What the system claims

The framework spec estimates 1.5 days per department with the 12-step onboarding checklist.

### Why this is partially overclaimed

**For write-capable departments (Finance, CIO, VCC):** 3-4 days is realistic for the first one, 2 days for subsequent ones. These need: custom Excel schema mappings, specific escalation rules, staging proposal formats, and specialist agents that understand the department's domain.

**For read-only departments (HR, Risk, Legal, IT, Comms, IB, IC):** A full LangGraph pipeline with 10+ nodes is over-engineered. Look at what a read-only department actually needs:

1. Receive a question
2. Embed the question
3. Search the department's Qdrant collections
4. Format the retrieved chunks
5. Ask the LLM to synthesize an answer
6. Return the answer

That is 5 steps. The template orchestrator has: `load_memory -> classify_intent -> retrieve_context -> [specialist routing to 3-4 agents] -> escalation_check -> notify_escalation -> excel_navigator -> validate_proposal -> staging_writer -> synthesise -> log_interaction -> create_paperclip_ticket -> END`.

8 of those nodes are irrelevant for read-only departments (excel_navigator, validate_proposal, staging_writer, notify_escalation, paperclip_ticket, and the specialist routing for departments where all agents do the same thing — answer questions).

**A single configurable read-only service could serve 7 departments** with department-specific config (which collections to search, which SKILL.md to load, which Slack channel to listen on). Instead, the plan creates 7 separate Docker containers running nearly identical code. That is 7x the deployment complexity, 7x the memory usage, and 7x the maintenance surface for zero additional capability.

---

## 7. "Comparable to Cloud APIs" (Qwen 122B Local)

### What the implicit claim is

By running Qwen 122B locally, the system provides GPT-4-level capabilities without sending data to external APIs.

### Where the gaps are real

| Task | Qwen 122B | GPT-4 / Claude | Impact on this system |
|------|-----------|----------------|----------------------|
| **JSON output** | ~80% valid on first attempt | ~98% (native JSON mode) | `validate_proposal.py` line 105 does `json.loads(raw)` with no retry. ~20% failure rate. `sdk_client.py` has 3 retries but still fails ~5% of runs. |
| **Instruction following** | ~80% fidelity to SKILL.md rules | ~90-95% | The SKILL.md says "NEVER average conflicting values." Qwen will sometimes do it anyway, especially in complex multi-source scenarios. |
| **Structured extraction** | Extracts simple values well | Handles complex/nested extraction | "The rate is approximately 3.15, subject to the revised facility terms" — Qwen may extract "3.15" or "approximately 3.15" or hallucinate. GPT-4 more reliably extracts "3.15" with appropriate caveats. |
| **Ambiguity handling** | Tends to hallucinate a confident answer | Tends to ask clarifying questions or express uncertainty | For corporate use, a hallucinated answer with wrong confidence is worse than "I'm not sure." Qwen 122B is more likely to produce the former. |
| **Multi-turn reasoning** | Degrades with context length | Maintains quality at length | The memory triad + SKILL.md + retrieved chunks + query can push to 8000+ tokens of preamble. Qwen's attention to the actual question degrades as preamble grows. |

**The local deployment is justified** by data residency requirements (corporate financial data should not leave the organization's infrastructure). But the team should budget 2x the prompt engineering effort and expect lower quality on complex queries.

---

## 8. Summary: What Each Feature Can Actually Do

| Feature | Marketing Label | Honest Label | What It Actually Does |
|---------|----------------|--------------|----------------------|
| Reflection Engine | Self-improving agents that learn from mistakes | Feedback logger with noisy LLM summaries | Appends daily interaction logs. Nightly LLM call produces memory notes of varying quality (~20% JSON failure rate, unknown accuracy of promoted facts). No mechanism to detect or correct bad memory entries. |
| Pattern Detector | AI detects quality degradation and proposes fixes | Threshold trigger on weak signal | Fires when >=5 interactions have avg approval score below 0.5 in 7 days. Not statistically meaningful. One extra rejection flips the trigger. Rate-limited to 1 per week to contain noise. |
| Memory Triad | Second brain that accumulates knowledge | Growing text file loaded into prompts | soul.md (useful, human-written). user.md (mostly empty). memory.md (accumulating LLM-generated notes of uncertain accuracy, consuming context window). |
| Heartbeat | Proactive agents that anticipate needs | Cron scheduler with stub data sources | APScheduler fires on cron. Context gatherers return hardcoded strings. All departments have it disabled. Zero real functionality. |
| Confidence Score | Calibrated quality indicator | Uncalibrated LLM self-report | The model outputs a number that sounds precise but has never been validated against ground truth. The 0.85 threshold is a guess. |
| Validation Node | Independent second opinion on proposals | Same model checking itself | Catches formatting errors and obvious hallucinations. Does not catch systematic biases. The history cross-check (comparing against recent proposals) is the genuinely useful part. |
| Citation System | Accurate source attribution | Best-effort source guessing | LLM sprinkles [N] references without verifying they match. Wrong source ~20-30% of the time. No grounding verification step. |
| 11 Departments | Scalable multi-department AI | Over-engineered for read-only depts | Write-capable (3 depts): justified complexity. Read-only (8 depts): a single configurable service would suffice instead of 8 Docker containers. |

---

## 9. What This Means for the Roadmap

### Ship now (these work)
- RAG Q&A for CAC committee (basic lookups)
- Staging pipeline with human approval (data safety is solid)
- Daily interaction logs (audit value, no AI interpretation needed)

### Ship with managed expectations (partially works)
- Excel proposals as "drafts for human review" (not "automated updates")
- Cross-department document search (will have noise in results)

### Defer (not ready)
- Reflection engine / self-improvement (produces noise, risk of memory corruption)
- Heartbeat / proactive agents (0% functional)
- 11-department expansion (validate core first, then expand)

### Rebrand (works differently than marketed)
- "Self-improving agents" -> "Feedback logging with optional AI-suggested prompt notes"
- "Confidence scoring" -> "Model-estimated relevance (unvalidated)"
- "Independent validation" -> "Automated format check + history comparison"
- "Proactive agents" -> "Scheduled task runner (not yet implemented)"
