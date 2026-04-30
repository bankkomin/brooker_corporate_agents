# Self-Improving Agents — What It Actually Does vs What It Sounds Like

**Date:** 2026-04-29
**Purpose:** Step-by-step walkthrough of the entire "self-improvement" loop, tracing real code, showing exactly what happens at each stage, and explaining where the gap between claim and reality lies.

---

## The Claim

> "Agents accumulate a second brain and self-improve from human feedback. The reflection engine nightly promotes raw logs into structured memory. The self-improvement actuator turns HOD approve/edit/reject signals into SKILL.md update proposals."
>
> — Phase 2 Framework Design Spec, Section 4

This sounds like: an AI that learns from its mistakes, gets smarter every day, and eventually rewrites its own behavior to be better.

---

## What Actually Happens — The Complete Chain

Let me trace the entire loop, step by step, through the actual code.

---

### Step 1: User asks a question in Slack (daytime)

A CAC committee member types in `#cac-committee`:

> "What's the current LCR ratio?"

The slack-bot receives this, forwards to `cac-orchestrator:3001/query`.

### Step 2: The orchestrator runs the LangGraph pipeline

`services/cac-orchestrator/src/graph.py` runs this chain:

```
load_memory → classify_intent → retrieve_context → [liquidity-agent] →
escalation_check → notify_escalation → excel_navigator → [validate?] →
synthesise → log_interaction → END
```

**load_memory** (`services/shared/load_memory.py` lines 11-36): Reads three files from disk:
- `obsidian-vault/cac/_memory/liquidity-agent/soul.md` — "I am the liquidity agent. I analyze LCR, NSFR..."
- `obsidian-vault/cac/_memory/liquidity-agent/user.md` — (initially empty)
- `obsidian-vault/cac/_memory/liquidity-agent/memory.md` — (initially empty)

These get concatenated into `state["agent_memory"]` and injected into every downstream LLM call as context. On day 1, this is maybe 50 tokens. After 30 days of reflection, this could be 2000+ tokens.

**synthesise** (`services/cac-orchestrator/src/nodes/synthesise.py`): Qwen 122B generates an answer:

> "The current LCR is 118.5% as of the latest ALCO Tracker update. [1] This is above the regulatory minimum of 100%. [2]"

The model also outputs `confidence_score: 0.91`.

### Step 3: The daily log is written

**log_interaction** (`services/shared/daily_log.py` lines 9-40): Appends an entry to `obsidian-vault/cac/daily-logs/2026-04-29.md`:

```markdown
## 14:23 · @U001 · proposal: none
**Q:** What's the current LCR ratio?
**A:** The current LCR is 118.5% as of the latest ALCO Tracker update. [1] This is above the regulatory minimum of 100%. [2]
**Citations:** alco_tracker.xlsx:LCR_tab:B5, regulatory_policy.pdf:p12
**Confidence:** 0.91
**Outcome:** pending
```

**This part works well.** It is a structured audit log. No AI interpretation, no risk of corruption. Pure value.

### Step 4: If a staging proposal was made, the HOD decides

Suppose the agent also proposed updating cell E8 to "118.5". The HOD opens the approval-ui, sees the proposal, and either:
- **Approves** it (clicks "Approve") — `approval_decisions.action = 'approved'`
- **Edits** it to "118.7" (types new value) — `approval_decisions.action = 'edited', edited_value = '118.7'`
- **Rejects** it (clicks "Reject") — `approval_decisions.action = 'rejected', rejection_reason = 'waiting for Q3 data'`

This decision is stored in Postgres. **This part also works well.** It is a human decision recorded in a database. No AI involved.

### Step 5: The outcome gets retroactively updated in the daily log

When the approval decision lands, the `Outcome` field in the daily log entry gets updated from `pending` to `approved` / `edited` / `rejected`. This is event-driven via Paperclip's event router.

**This is where the "self-improvement" narrative begins and where reality starts diverging from the claim.**

---

### Step 6: 02:00 AM — The reflection engine wakes up

`services/reflection-engine/src/scheduler.py` fires a nightly cron. For each live department, it calls `run_dept_reflection()` in `engine.py`.

Here is exactly what happens for the CAC department:

#### 6a. Read yesterday's daily log

`engine.py` lines 28-34:
```python
yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
log_path = dept_vault / "daily-logs" / f"{yesterday}.md"
entries = parse_daily_log(log_path)
```

`log_reader.py` parses the markdown file into structured `LogEntry` objects. Suppose yesterday had 5 interactions:

```
- [09:15] @U001: Q=What is the current LCR? → outcome=approved
- [10:30] @U002: Q=Update the NSFR to 104.2 → outcome=edited
- [11:00] @U001: Q=What are the funding facility rates? → outcome=approved
- [14:00] @U003: Q=Show me the Q3 covenant status for EU sub → outcome=pending
- [16:00] @U002: Q=Set capital ratio to 15.8 → outcome=rejected
```

**What's real:** This is just reading a text file. It works. No AI involved yet.

#### 6b. Fetch approval decisions from Postgres

`decisions_joiner.py` lines 20-42:
```python
rows = await conn.fetch("""
    SELECT agent_id, proposal_id, action, signal_strength, rejection_reason, edited_value
    FROM agent_performance
    WHERE dept_id = $1 AND created_at > NOW() - make_interval(days => $2)
""", dept_id, days)
```

This queries the `agent_performance` view which computes `signal_strength`:
- approved → 1.0
- edited (118.5 → 118.7) → 0.5 + 0.5 * (1 - |118.5-118.7|/118.5) = 0.999
- rejected → 0.0

Result:
```
- proposal chg_1001: approved (signal=1.00)
- proposal chg_1002: edited (signal=0.999)
- proposal chg_1004: rejected (signal=0.00)
```

**What's real:** This is a database query. The signal_strength formula works for numeric values. It is a crude but functional quality proxy.

**What's overclaimed:** The signal doesn't capture WHY the HOD rejected. "Rejected because waiting for Q3 data" is not the agent's fault — the agent was correct, just premature. But the system records signal=0.0, identical to "rejected because totally wrong." There is no way to distinguish "wrong answer" from "right answer, wrong time."

#### 6c. Fetch knowledge gaps

`decisions_joiner.py` lines 45-58:
```python
rows = await conn.fetch("""
    SELECT agent_id, query, hit_count, llm_self_report, expected_doc_type
    FROM agent_knowledge_gaps
    WHERE dept_id = $1 AND created_at > NOW() - make_interval(days => $2)
      AND resolved_at IS NULL
""", dept_id, days)
```

Suppose one gap was recorded because the EU subsidiary query (entry #4) had < 3 Qdrant hits:
```
- liquidity-agent: 'Show me the Q3 covenant status for EU sub' (hits=1)
```

**What's real:** This is genuinely useful. It tells you "the agent couldn't find data for this query." This is the most actionable output of the entire self-improvement loop — it creates a backlog of documents that should be ingested.

---

### Step 7: The LLM "reflects" — THIS IS WHERE THE OVERCLAIM LIVES

`engine.py` lines 74-82 calls `run_reflection_llm()` for EACH agent in the department:

```python
sdk_output = await run_reflection_llm(
    dept_id="cac",
    agent_id="liquidity-agent",
    daily_log=daily_log_text,
    decisions=decisions_text,
    gaps=gaps_text,
    current_memory=current_memory,
    current_user=current_user,
)
```

This calls `sdk_client.py` which sends this prompt to Qwen 122B:

```
You are a reflection agent for the cac department's liquidity-agent agent.
Analyze yesterday's interactions and approval decisions, then determine what
should be updated in the agent's persistent memory.

Yesterday's daily log entries:
- [09:15] @U001: Q=What is the current LCR? → outcome=approved
- [10:30] @U002: Q=Update the NSFR to 104.2 → outcome=edited
- [11:00] @U001: Q=What are the funding facility rates? → outcome=approved
- [14:00] @U003: Q=Show me the Q3 covenant status for EU sub → outcome=pending
- [16:00] @U002: Q=Set capital ratio to 15.8 → outcome=rejected

Approval decisions on staging proposals:
- proposal chg_1001: approved (signal=1.00)
- proposal chg_1002: edited (signal=0.999)
- proposal chg_1004: rejected (signal=0.00)

Knowledge gaps identified:
- liquidity-agent: 'Show me the Q3 covenant status for EU sub' (hits=1)

Current memory.md:
# Memory
## Lessons
No lessons yet.

Current user.md:
# User

Output a JSON object with exactly these keys:
{
  "memory_md_updates": [...],
  "user_md_updates": [...],
  "skill_proposals": [...]
}
```

#### What Qwen 122B actually produces

On a **good day** (~60% of the time), something like:

```json
{
  "memory_md_updates": [
    {"section": "Lessons", "content": "LCR and funding queries are consistently well-handled. Capital ratio proposals should be cross-checked against Q3 data availability before proposing. EU subsidiary covenant data is not available in the current knowledge base."},
    {"section": "Patterns", "content": "User U001 frequently asks about LCR metrics. User U002 tends to submit numeric updates that sometimes need small adjustments."}
  ],
  "user_md_updates": [
    {"section": "U001", "content": "Frequently asks about LCR. Prefers percentage format."},
    {"section": "U002", "content": "Submits numeric updates. Values sometimes need minor corrections (e.g., NSFR 104.2 → 104.8)."}
  ],
  "skill_proposals": []
}
```

On a **bad day** (~20% of the time):

```
I'll analyze the interactions and provide memory updates.

Based on yesterday's data, here are my recommendations:
```json
{
  "memory_md_updates": [
```

...and the JSON parsing fails because the model wrapped it in explanatory text. The 3-retry loop tries again. After 3 failures, returns empty arrays. The night produces nothing.

On a **mediocre day** (~20% of the time):

```json
{
  "memory_md_updates": [
    {"section": "Lessons", "content": "The agent handled 5 interactions yesterday. 2 were approved, 1 was edited, 1 was rejected, and 1 is pending."}
  ],
  "user_md_updates": [],
  "skill_proposals": []
}
```

This is a summary, not a lesson. It wastes tokens when loaded into future prompts without adding any useful guidance.

#### The four specific problems with this step

**Problem A: The LLM has no domain expertise about what makes a good "lesson."**

The prompt says "only promote facts you are highly confident about." But Qwen 122B doesn't know what a useful financial insight looks like. It sees "capital ratio proposal was rejected" and might conclude "capital ratio proposals should be avoided" — when the real lesson is "check if Q3 data is published before proposing capital updates." The model cannot distinguish between these because it does not understand the committee's workflow.

A human financial analyst would know that the rejection was about timing, not accuracy. The model sees only: proposed=15.8, action=rejected, signal=0.0. It has no way to read the rejection_reason in context.

**Problem B: The model hallucinates patterns from tiny samples.**

From 5 interactions, the model confidently writes "User U001 frequently asks about LCR." One query is not "frequently." But the model treats the instruction "detect patterns" as license to find patterns whether they exist or not. After 30 days, memory.md might claim "User U001 always prefers consolidated figures" based on 3 queries where U001 happened to ask about consolidated data — not because of preference, but because those happened to be the topics that day.

**Problem C: The model cannot distinguish its own hallucinations from real observations.**

If yesterday the agent hallucinated "The covenant threshold is 100%" (it's actually 110%), and the HOD rejected the proposal, the model might write in memory.md: "Covenant threshold should be verified — proposed 100% but was rejected." This is useful. But it might also write: "Covenant threshold is under review and may be changing from 110% to 100%." This is a fabrication that sounds authoritative and will pollute all future covenant queries.

**Problem D: There is no mechanism to evaluate the quality of these updates.**

The LLM writes to memory.md. Nobody checks if the updates are correct. The archive-before-overwrite (`promoter.py` lines 60-75) saves the old version, but nobody reviews the archive. The updates accumulate silently. The only way to detect a bad update is when the agent starts giving wrong answers that trace back to a corrupted memory entry — and by then, multiple entries may be corrupted.

---

### Step 8: The promoter writes to memory.md

`promoter.py` lines 33-57:

```python
def promote_memory(mem_dir: Path, sdk_output: dict) -> dict:
    changes = {"memory_updated": False, "user_updated": False, "archived": []}

    memory_updates = sdk_output.get("memory_md_updates", [])
    if memory_updates:
        memory_file = mem_dir / "memory.md"
        _archive_file(memory_file, mem_dir, changes)   # copy old to history/
        _apply_updates(memory_file, memory_updates)     # overwrite with new
        changes["memory_updated"] = True
```

After `_apply_updates`, `memory.md` now contains:

```markdown
## Lessons
LCR and funding queries are consistently well-handled. Capital ratio proposals
should be cross-checked against Q3 data availability before proposing. EU
subsidiary covenant data is not available in the current knowledge base.

## Patterns
User U001 frequently asks about LCR metrics. User U002 tends to submit numeric
updates that sometimes need small adjustments.
```

The old `memory.md` ("No lessons yet.") is saved to `history/2026-04-29-memory.md`.

**What's real:** A file was written. An archive was kept. The mechanics work.

**What's overclaimed:** The content of that file is LLM-generated text of unknown accuracy. It might be useful ("cross-check Q3 data before proposing capital updates") or it might be noise ("User U001 frequently asks about LCR" — based on 1 query). There is no quality filter between the LLM output and the file write, other than the sanitizer that blocks HTML tags and prompt injection strings.

---

### Step 9: Tomorrow morning — the memory gets loaded into every query

When User U001 asks another question tomorrow, `load_memory_node()` in `services/shared/load_memory.py` reads:

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

Now every LLM call for the liquidity-agent starts with:

```
[soul.md - ~100 tokens]
I am the liquidity agent for the CAC committee. I analyze LCR, NSFR...

---

[user.md - ~60 tokens]
## U001
Frequently asks about LCR. Prefers percentage format.
## U002
Submits numeric updates. Values sometimes need minor corrections.

---

[memory.md - ~120 tokens]
## Lessons
LCR and funding queries are consistently well-handled...
## Patterns
User U001 frequently asks about LCR metrics...
```

That is ~280 tokens of preamble on day 2. After 30 days, it could be 1000-2000 tokens. After 90 days, it could be 3000-5000 tokens.

**The accumulation problem:** Each night adds new content but rarely removes old content. `_apply_updates` (promoter.py line 78) replaces sections by name — so if the LLM always uses section name "Lessons," the old content gets replaced. But if the LLM uses different section names on different nights ("Lessons," "Key Takeaways," "Observations," "Daily Notes"), each becomes a new section that persists forever.

After 90 days, memory.md might look like:

```markdown
## Lessons
[latest night's lessons]

## Patterns
[latest night's patterns]

## Key Takeaways
[from night 12, never overwritten because the LLM used a different section name]

## Observations
[from night 23]

## Recurring Issues
[from night 45]

## User Preferences
[from night 67, partially contradicts the user.md entries]
```

Each of these sections gets loaded into every prompt. The model must read through all of them to find the relevant bits. This is the opposite of "getting smarter" — it is getting noisier.

---

### Step 10: Pattern detection — skill proposals

`pattern_detector.py` runs after all agents are processed:

```python
rows = await conn.fetch("""
    SELECT ap.dept_id, ai.agent_id, COUNT(*) AS n, AVG(ap.signal_strength) AS avg_signal
    FROM agent_performance ap
    JOIN agent_interactions ai ON ai.id = (...)
    WHERE ap.dept_id = $1 AND ap.created_at > NOW() - INTERVAL '7 days'
    GROUP BY ap.dept_id, ai.agent_id
    HAVING COUNT(*) >= 5 AND AVG(ap.signal_strength) < 0.5
""", dept_id, threshold_count, signal_max)
```

**What this actually measures:** "Did this agent have 5+ proposals in the last 7 days where the average HOD approval score was below 0.5?"

**Why this is almost always noise:**

Scenario A — Agent is fine, HOD is busy:
| Day | Proposal | HOD Action | Signal | Reason |
|-----|----------|-----------|--------|--------|
| Mon | LCR=118.5 | Approved | 1.0 | Correct |
| Tue | NSFR=104.2 | Approved | 1.0 | Correct |
| Wed | Capital=15.8 | Rejected | 0.0 | "Waiting for board meeting" |
| Thu | Funding=2.1 | Rejected | 0.0 | "Let me check this myself" |
| Fri | Covenant=95% | Rejected | 0.0 | "Need to discuss with legal first" |

Average: 0.4. Trigger fires. **But the agent was correct every time.** The rejections were about process, not accuracy.

Scenario B — Agent is actually bad:
| Day | Proposal | HOD Action | Signal | Reason |
|-----|----------|-----------|--------|--------|
| Mon | LCR=118.5 | Edited to 120.1 | 0.99 | Small correction |
| Tue | NSFR=104.2 | Edited to 108.7 | 0.96 | Moderate correction |
| Wed | Capital=15.8 | Edited to 14.2 | 0.93 | Off by a bit |
| Thu | Funding=2.1 | Edited to 2.4 | 0.94 | Off by a bit |
| Fri | Covenant=95% | Edited to 88% | 0.93 | Off by a lot |

Average: 0.95. Trigger does NOT fire. **But the agent was consistently wrong.** Every value was off. The formula gives high scores because the numeric distance was small relative to the absolute values.

**The signal is broken in both directions.** It fires on good agents with bad luck, and stays silent on bad agents with small errors.

---

### Step 11: If the pattern detector fires — skill proposal

When a proposal is inserted into `agent_skill_proposals`, it shows up in the approval-ui's "Skill Updates" tab. The HOD sees:

> **Skill Update Proposal**
> cac / liquidity-agent
> Trigger: avg signal 0.38 over 6 interactions in 7d
> Evidence: {"count": 6, "avg_signal": 0.38}
> Proposed Changes: (none yet — awaiting OpenClaw draft)

The HOD must click "Approve" or "Reject." If approved, OpenClaw (a coding worker) reads the skill file + evidence and drafts a SKILL.md change as a PR.

**What the HOD actually sees:** A vague alert that says "this agent had a bad week." No specific guidance on what to change. The HOD must investigate why the signal was low, which requires reading the daily logs manually — exactly the work the "self-improvement" system was supposed to automate.

---

## Summary: The Complete Loop

```
Day 1: User asks question → agent answers → daily log written ← WORKS
        HOD approves/rejects → approval_decisions table ← WORKS
        
Night 1: Cron fires at 02:00
         → Read daily log ← WORKS (file parsing)
         → Read approval decisions ← WORKS (SQL query)
         → Read knowledge gaps ← WORKS (SQL query)
         → Ask Qwen 122B to "reflect" ← UNRELIABLE (~60% useful, ~20% noise, ~20% JSON failure)
         → Write LLM output to memory.md ← WORKS mechanically, content quality unknown
         → Check if pattern detector triggers ← UNRELIABLE (5 data points, broken signal)
         
Day 2: User asks question
       → load_memory reads memory.md ← WORKS (file read)
       → memory.md content injected into LLM prompt ← WORKS mechanically
       → LLM may or may not benefit from the memory content ← UNKNOWN, untested
       → If bad content in memory, agent gives worse answers ← RISK
```

### What "self-improving" actually means in this system:

1. An LLM writes notes about itself to a file (sometimes useful, sometimes noise, sometimes wrong)
2. Those notes are loaded into future prompts (consuming context window)
3. A crude statistical trigger occasionally suggests the agent needs help (based on weak signal)
4. A human must manually review and approve any actual behavior changes

### What it sounds like it means:

1. The agent learns from every interaction
2. It automatically adapts its behavior
3. It gets measurably better over time
4. Mistakes are systematically eliminated

### The gap:

The system has no mechanism to measure whether it is getting better. There is no before/after comparison. There is no A/B test. There is no accuracy metric that trends over time. The word "improvement" implies measured progress — but there is no measurement.

**What would actual self-improvement require:**
- A labeled evaluation dataset (questions with known correct answers)
- A/B testing: agent with memory vs agent without memory
- Systematic prompt optimization (not LLM-generated notes, but structured prompt changes validated against the eval set)
- Human-curated memory that is reviewed weekly, not auto-generated nightly

**What this system actually provides:**
- An audit trail (daily logs) — genuinely valuable
- A knowledge gap backlog (agent_knowledge_gaps table) — genuinely valuable
- LLM-generated memory notes — marginal value, risk of corruption
- A noise-prone statistical trigger — marginal value, mostly false positives
