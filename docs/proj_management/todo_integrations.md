# TODO — External Integrations

Slack, Email, SharePoint, SFTP, and other external system connections.

---

## P0 — Critical

### [ ] Create and configure Slack app
- Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
- **Required bot token scopes:**
  - `channels:history`, `channels:read`, `chat:write`, `files:read`, `app_mentions:read`, `reactions:write`
- **Event subscriptions:** Enable Events API, set request URL to `https://<host>:3003/slack/events`
- **Events:** `message.channels`, `file_shared`, `app_mention`
- Set env vars: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN`
- Create channels: `#cac-committee`, `#escalations`, `#cac-approvals`
- Install app to workspace and invite bot to all channels

### [ ] Add `/post-escalation` endpoint to slack-bot
- **Audit finding (API-4)** — paperclip calls this endpoint but it doesn't exist
- `services/paperclip/src/services/event_router.py:197-201` POSTs to `http://slack-bot:3003/post-escalation`
- slack-bot only has `/slack/events` and `/health`
- **Fix:** Add endpoint that accepts `{escalation_detail, department, severity}` and posts to #escalations channel
- **File:** `services/slack-bot/src/main.py`

---

## P1 — High

### [ ] Configure email provider
- **Option A — SMTP:** Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` in `.env`
- **Option B — SendGrid:** Set `SENDGRID_API_KEY` in `.env`
- **Option C — Microsoft Graph API:** Set `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_TENANT_ID`
- Test with MailHog first: `docker compose -f docker-compose.yml -f docker-compose.test.yml up`
- MailHog UI at `http://localhost:8025`

### [ ] Set up HOD email addresses
- Populate in `.env`: `HOD_EMAIL_CAC=<real-email>`
- CEO/CFO emails: `CEO_EMAIL`, `CFO_EMAIL`
- **Note:** `config/departments.json` has `"${CAC_HOD_EMAIL}"` shell syntax which JSON doesn't interpolate — see todo_frontend.md

### [ ] Implement sync-mirror SharePoint connector
- `services/sync-mirror/src/connectors/sharepoint.py` is a stub
- Needs: real implementation using `smbprotocol` or Microsoft Graph API
- Must pull corporate Excel files into `/data/mirror/`
- **Dependencies:** SharePoint site URL, credentials, document library path

### [ ] Implement sync-mirror SFTP connector
- `services/sync-mirror/src/connectors/sftp.py` is a stub
- Needs: real implementation using `paramiko` (already in requirements.txt)
- **Dependencies:** SFTP host, port, username, key/password

---

## P2 — Medium

### [ ] Configure sync-back corporate write-back
- `sync-back` currently modifies a local copy — needs connector to push back to SharePoint/SFTP
- Most sensitive operation — verify audit trail is complete

### [ ] Test email deep-link flow end-to-end
- Email-notifier generates JWT deep-links for HOD approval
- Link format: `https://<approval-ui-host>:4000/proposals/<id>?token=<jwt>`
- Must test: email received -> click link -> UI loads -> JWT validates -> proposal displayed

---
*Last updated: 2026-04-10*
