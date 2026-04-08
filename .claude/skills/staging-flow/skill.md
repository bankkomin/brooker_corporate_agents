---
name: staging-flow
description: Build and test the staging pipeline — manifest schema validation, staging_writer, approval-ui integration, sync-back watchdog, email-notifier triggers. Use when working on the proposal-to-approval data flow.
---

## Staging Pipeline Workflow

### Pipeline Overview
```
Agent confidence ≥ 0.85
  → staging_writer.py writes manifest to /data/staging/pending/
  → Paperclip ticket created
  → Slack #approvals notification
  → email-notifier POST /notify/proposal → HOD email
  → HOD clicks "Review Now" link → approval-ui
  → HOD decides: approve / edit+approve / reject / defer
  → If approved: move to approved/ → sync-back writes to corporate → archive
  → If approved: email-notifier POST /notify/confirmed (optional)
  → If rejected: move to rejected/ → nothing syncs
```

### 1. Manifest Schema
Every proposal in `/data/staging/pending/` must be a JSON file matching:
```json
{
  "id": "chg_XXXX",
  "created_at": "ISO8601",
  "agent": "funding-agent",
  "triggered_by": "app_mention",
  "slack_user": "U12345678",
  "file": "ALCO_Tracker.xlsx",
  "tab": "Funding Facilities",
  "cell": "E8",
  "old_value": null,
  "new_value": "3.15",
  "source": "Slack #cac-committee | Jane Doe | 2026-03-24T10:42",
  "source_excerpt": "current net debt/EBITDA is 3.15x",
  "confidence": 0.91,
  "reasoning": "...",
  "status": "pending",
  "paperclip_ticket_id": "PPC-0142"
}
```

### 2. staging_writer.py Implementation
- Validate manifest against Pydantic model before writing
- Generate sequential `chg_XXXX` IDs (query Postgres for last ID)
- Write JSON to `/data/staging/pending/chg_XXXX.json`
- Insert row into `staging_proposals` Postgres table
- POST to Paperclip API to create ticket
- POST to Slack #approvals channel
- POST to email-notifier `/notify/proposal`

### 3. approval-ui Integration
- `GET /queue` — list all files in staging/pending/
- `GET /queue/{id}` — read manifest, show diff view
- `POST /queue/{id}/approve` — move to approved/, update Postgres, trigger sync-back
- `POST /queue/{id}/reject` — move to rejected/, log reason
- `POST /queue/{id}/defer` — keep in pending, set reminder
- On approve: POST email-notifier `/notify/confirmed` (if enabled)

### 4. sync-back Integration
- watchdog watches `staging/approved/`
- On new file: read manifest → write to corporate (openpyxl) → verify → archive
- On failure: rollback + alert #escalations + email HOD

### 5. Testing the Full Loop
```bash
# 1. Create a test proposal manually
echo '{"id":"chg_test","file":"ALCO_Tracker.xlsx",...}' > /data/staging/pending/chg_test.json

# 2. Verify it appears in approval-ui
curl http://localhost:4000/queue

# 3. Approve it
curl -X POST http://localhost:4000/queue/chg_test/approve

# 4. Verify sync-back triggered
ls /data/staging/approved/
ls /data/archive/

# 5. Verify email sent (check email_log table)
```

### 6. Key Invariants to Test
- Proposals with confidence < 0.85 are NEVER created
- Rejected proposals NEVER reach sync-back
- Every approval has approver ID + timestamp in Postgres
- Archive entries are immutable (append-only)
- Email deep-link URL contains correct proposal_id
