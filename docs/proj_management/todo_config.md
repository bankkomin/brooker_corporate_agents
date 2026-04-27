# TODO — Configuration

Environment variables, JSON configs, JWT keys, and schema files.

---

## P0 — Critical

### [ ] Create `.env` from `.env.example`
- Copy `.env.example` to `.env` at project root
- Fill in all required values (120+ variables)
- Key sections: Slack, LLM, Postgres, MinIO, Email, Auth, Paperclip, HOD emails
- Never commit `.env` to git (already in `.gitignore`)

### [ ] Generate JWT RS256 key pair
- Run: `bash scripts/generate-jwt-keys.sh`
- Creates `secrets/jwt_private.pem` and `secrets/jwt_public.pem`
- Used by: gateway (token validation), email-notifier (deep-link signing), approval-ui (link verification)
- Docker Compose mounts these as Docker secrets

### [ ] Populate `config/excel_schema/alco_tracker.json` with real Excel structure
- **Status:** [x] Done — expanded from 1 tab to 4 tabs (Funding Facilities, Liquidity, Capital, ALM)
- Cell references match SKILL.md files
- **Remaining:** Verify against actual `ALCO_Tracker.xlsx` structure when available

---

## P1 — High

### [ ] Expand `config/escalation_rules.json` with all business triggers
- **Status:** [x] Done — expanded from 2 to 10 triggers with thresholds from SKILL.md files
- Includes: car, cet1, lcr, nsfr, duration_gap, facility_utilization, interest_coverage, etc.

### [ ] Fix `departments.json` containing un-interpolated shell variable syntax
- **Audit finding (FE-11)** — literal `"${CAC_HOD_EMAIL}"` used as email address
- `config/departments.json:19` — `hodEmails`, `slackChannels` have `"${VAR}"` syntax
- JSON does not support shell variable expansion — values are literal strings
- **Fix options:**
  - A) Replace with actual values at deployment time
  - B) Generate config from a template script at deploy (e.g., `envsubst < departments.json.tmpl > departments.json`)
  - C) Have services resolve `${VAR}` patterns via `os.environ.get()` (email-notifier already does this)
- **Verify:** Which services parse these vars and which don't

### [ ] Verify `hod_emails.json` and `dept_channels.json` references
- **Status:** [x] Done — confirmed these don't exist as standalone files, all services read from `departments.json`
- CLAUDE.md updated to reflect this

### [ ] Standardise model names across services and .env
- **Audit finding (AI-H1)** — model name differs between 3 locations
- `cac-orchestrator/config.py:16` defaults to `"qwen-122b"`
- `wiki-compiler/config.py:9` defaults to `"qwen-3.5-122b"`
- `.env.example` uses `VLLM_LARGE_MODEL=qwen-large`
- **Fix:** Pick one canonical name matching `--served-model-name` in vLLM start script

### [ ] Standardise env var names across services
- **Audit finding (API-15)** — `STAGING_DIR` vs `STAGING_PATH` inconsistency
- paperclip reads `STAGING_DIR`, docker-compose sets `STAGING_PATH`
- sync-back defaults to wrong database name (`brooker_agent` vs `corporate_agents`)
- **Fix:** Audit all services for env var naming; standardise and document in `.env.example`

---

## P2 — Medium

### [ ] Review `config/departments.json` for completeness
- Currently only defines `cac` department
- HR department structure needs to be added when HR goes live
- Global roles (CEO, CFO) are defined but verify email addresses are populated
- Slack channel IDs use `${SLACK_CHANNEL_*}` substitution — confirm env vars are set

### [ ] Update `CLAUDE.md` config file references
- **Status:** [x] Done — removed references to standalone `hod_emails.json` and `dept_channels.json`

---
*Last updated: 2026-04-10*
