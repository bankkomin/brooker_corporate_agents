---
description: Verify data zone enforcement in Docker configuration
---
Use the security-auditor subagent to verify data zone enforcement.

Check:
1. Read `docker-compose.yml` — verify all volume mounts follow data zone rules:
   - Agent containers: `mirror_data:/data/mirror:ro` (read-only)
   - Only sync-mirror: `mirror_data:/data/mirror:rw`
   - Only cac-orchestrator + approval-ui: `staging_data:/data/staging:rw`
   - Only sync-back: `archive_data:/data/archive:rw`

2. Search codebase for any code that writes to `/data/mirror/` — must find NONE.

3. Search for any direct file system writes outside of `staging_writer.py` — flag violations.

4. Verify `.env.example` has `STAGING_PATH`, `MIRROR_PATH`, `ARCHIVE_PATH` defined.

Report: PASS/FAIL for each check with details.
