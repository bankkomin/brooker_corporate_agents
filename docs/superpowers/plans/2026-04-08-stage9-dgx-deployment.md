# Stage 9 — Production Deployment Checklist

> Wiki RAG Knowledge Base — production deployment and integration testing.
> All unit tests pass on dev machine (546 total, 90 wiki-compiler specific). This checklist covers Docker build, service integration, and E2E validation.

## Network Architecture

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│  Windows Production PC       │     │  DGX Spark (LLM Host)        │
│                              │     │                              │
│  Docker Desktop              │     │  vLLM:                       │
│  ├─ postgres     :5432       │     │  ├─ Qwen3.5 122B  :8000     │
│  ├─ qdrant       :6333       │     │  └─ Qwen3.5 9B    :8002     │
│  ├─ minio        :9000       │     │                              │
│  ├─ gateway      :3000       │     │  IP: ${DGX_SPARK_IP}        │
│  ├─ orchestrator :3001       │     │  (e.g., 192.168.1.100)      │
│  ├─ slack-bot    :3003       │     └──────────────────────────────┘
│  ├─ rag-ingest   :3004       │              ▲
│  ├─ email-notify :3005       │              │ HTTP
│  ├─ sync-back    :3006       │              │ (ports 8000, 8002)
│  ├─ wiki-compiler:3007  ─────┼──────────────┘
│  ├─ paperclip    :3100       │
│  ├─ approval-ui  :4000       │
│  └─ nginx        :8080       │
└──────────────────────────────┘
```

**Key:** Docker containers on the Windows PC call the DGX Spark LLM via `extra_hosts` mapping
`host.docker.internal` → DGX Spark's IP address (NOT localhost).

**Prerequisites:**
- DGX Spark running with vLLM (Qwen3.5 122B on port 8000, Qwen3.5 9B embed on port 8002)
- DGX Spark IP accessible from Windows PC (test: `curl http://<DGX_IP>:8000/v1/models`)
- Docker Desktop installed on Windows PC
- Git repo synced to latest main with Stage 9 code

---

## Phase 0: Network Setup (CRITICAL)

- [ ] **0.1** Find DGX Spark IP address:
  ```bash
  # On DGX Spark:
  hostname -I
  # Or from Windows PC:
  ping dgx-spark   # if hostname resolves
  ```
  Record the IP: `DGX_SPARK_IP=_______________`

- [ ] **0.2** Test LLM connectivity from Windows PC:
  ```bash
  curl -s http://<DGX_SPARK_IP>:8000/v1/models | jq .
  curl -s http://<DGX_SPARK_IP>:8002/v1/models | jq .
  ```
  Expected: Both return model info JSON

- [ ] **0.3** Update `docker-compose.yml` — replace `host.docker.internal:host-gateway` with DGX Spark IP

  The current `extra_hosts` mapping points to localhost (which is correct when LLM is on the same machine).
  For a separate DGX Spark, you need to change ALL services that call vLLM:

  **Option A: Edit extra_hosts directly** (per service):
  ```yaml
  extra_hosts:
    - "host.docker.internal:<DGX_SPARK_IP>"
  ```
  This makes `host.docker.internal` resolve to the DGX Spark inside every container.
  Services that need this: `wiki-compiler`, `rag-ingestion`, `cac-orchestrator`, `nginx`.

  **Option B: Use .env file** (recommended — single place to change):
  Create/update `.env` in project root:
  ```bash
  DGX_SPARK_IP=192.168.1.100   # Replace with actual IP
  ```
  Then in `docker-compose.yml`, use variable substitution:
  ```yaml
  extra_hosts:
    - "host.docker.internal:${DGX_SPARK_IP}"
  ```

- [ ] **0.4** Also update `VLLM_BASE_URL` environment vars if they reference `host.docker.internal`:
  ```yaml
  # These should remain as host.docker.internal (resolved by extra_hosts)
  VLLM_BASE_URL=http://host.docker.internal:8000/v1
  ```
  This works because Step 0.3 maps `host.docker.internal` → DGX Spark IP.

- [ ] **0.5** Verify DGX Spark firewall allows inbound on ports 8000 and 8002 from Windows PC

---

## Phase 1: Build & Start

- [ ] **1.1** `git pull origin main` — sync Stage 9 code to Windows production PC
- [ ] **1.2** Verify new files exist:
  ```bash
  ls services/wiki-compiler/Dockerfile
  ls services/wiki-compiler/src/main.py
  ls config/wiki_schema.json
  ls skills/shared/wiki-maintenance.md
  ls obsidian-vault/cac/index.md
  ```
- [ ] **1.3** Build wiki-compiler image:
  ```bash
  docker compose build wiki-compiler
  ```
- [ ] **1.4** Start wiki-compiler alongside existing services:
  ```bash
  docker compose up -d wiki-compiler
  ```
- [ ] **1.5** Verify health endpoint:
  ```bash
  curl -s http://localhost:3007/health | jq .
  ```
  Expected: `{"service": "wiki-compiler", "status": "healthy", "version": "0.1.0"}`

- [ ] **1.6** Check container logs for startup errors:
  ```bash
  docker compose logs wiki-compiler --tail 20
  ```
  Expected: No errors, "startup" log entry visible

---

## Phase 2: Config Verification

- [ ] **2.1** Verify vault mount is `:rw` in wiki-compiler:
  ```bash
  docker compose exec wiki-compiler ls -la /mnt/obsidian-vault/cac/
  ```
  Expected: `index.md`, `log.md`, `concepts/`, `decisions/`, etc.

- [ ] **2.2** Verify vault mount is still `:ro` in rag-ingestion:
  ```bash
  docker compose exec rag-ingestion touch /mnt/obsidian-vault/test-write 2>&1
  ```
  Expected: `touch: cannot touch '/mnt/obsidian-vault/test-write': Read-only file system`

- [ ] **2.3** Verify wiki_schema.json is accessible:
  ```bash
  docker compose exec wiki-compiler cat /app/config/wiki_schema.json | jq .version
  ```
  Expected: `"1.0"`

- [ ] **2.4** Verify departments.json has vaultPath:
  ```bash
  docker compose exec wiki-compiler cat /app/config/departments.json | jq '.departments.cac.dataAccess.vaultPath'
  ```
  Expected: `"/mnt/obsidian-vault/cac"`

- [ ] **2.5** Verify obsidian_watch.json has department-scoped paths:
  ```bash
  docker compose exec rag-ingestion cat /app/config/obsidian_watch.json | jq '.watch_folders | length'
  ```
  Expected: `11`

---

## Phase 3: Compile Endpoint — Direct Test

- [ ] **3.1** POST a test proposal_approved event:
  ```bash
  curl -s -X POST http://localhost:3007/compile \
    -H "Content-Type: application/json" \
    -d '{
      "event_type": "proposal_approved",
      "dept_id": "cac",
      "payload": {
        "proposal_id": "chg_test_001",
        "agent": "funding-agent",
        "file": "ALCO_Tracker.xlsx",
        "tab": "Funding Facilities",
        "cell": "E8",
        "old_value": "72",
        "new_value": "78",
        "source": "Slack #cac-committee | Test User | 2026-04-08T10:00",
        "confidence": 0.91,
        "reasoning": "Test: Updated based on latest facility draw notification",
        "reviewer": "test@brooker.co.th"
      }
    }' | jq .
  ```
  Expected: `{"status": "compiled", "article_path": "cac/decisions/...", "pages_updated": [...]}`

- [ ] **3.2** Verify article was written to vault:
  ```bash
  ls -la obsidian-vault/cac/decisions/
  ```
  Expected: New `.md` file with today's date in filename

- [ ] **3.3** Read the generated article and verify frontmatter:
  ```bash
  head -20 obsidian-vault/cac/decisions/2026-04-08-*.md
  ```
  Expected: YAML frontmatter with `type: decision`, `department: cac`, `confidence: high`

- [ ] **3.4** Verify index.md was updated:
  ```bash
  cat obsidian-vault/cac/index.md | grep "decisions"
  ```
  Expected: New entry under `## Decisions` section

- [ ] **3.5** Verify log.md was appended:
  ```bash
  tail -5 obsidian-vault/cac/log.md
  ```
  Expected: `## [2026-04-08] ingest | ...` entry

- [ ] **3.6** Check compilation time in wiki-compiler logs:
  ```bash
  docker compose logs wiki-compiler --tail 5 | grep "compiled"
  ```
  Expected: Compilation latency < 30s

---

## Phase 4: VaultWatcher Integration

- [ ] **4.1** Restart rag-ingestion to pick up updated obsidian_watch.json:
  ```bash
  docker compose restart rag-ingestion
  ```

- [ ] **4.2** Wait 10 seconds for VaultWatcher to initialize and detect the new article

- [ ] **4.3** Check rag-ingestion logs for vault ingestion:
  ```bash
  docker compose logs rag-ingestion --tail 20 | grep "vault_watcher"
  ```
  Expected: `vault_watcher.ingested` entry with the new article path and correct collection

- [ ] **4.4** Verify article is in Qdrant cac_knowledge collection:
  ```bash
  curl -s http://localhost:6333/collections/cac_knowledge | jq '.result.points_count'
  ```
  Expected: Count increased from previous value

- [ ] **4.5** Search Qdrant for the test article content:
  ```bash
  curl -s -X POST http://localhost:3004/search \
    -H "Content-Type: application/json" \
    -d '{"query": "funding facility utilization 78%", "collection": "cac_knowledge", "limit": 3}' | jq .
  ```
  Expected: Search results include content from the generated decision article

---

## Phase 5: Paperclip Event Routing

- [ ] **5.1** Verify WIKI_COMPILER_URL is set in Paperclip container:
  ```bash
  docker compose exec paperclip env | grep WIKI_COMPILER
  ```
  Expected: `WIKI_COMPILER_URL=http://wiki-compiler:3007`

- [ ] **5.2** Trigger an approval through the approval-ui or API:
  ```bash
  # Create a test staging proposal first
  echo '{"id":"chg_test_002","agent":"liquidity-agent","file":"ALCO_Tracker.xlsx","tab":"Liquidity","cell":"D8","old_value":"110","new_value":"115","source":"test","confidence":0.88,"reasoning":"test","status":"pending"}' > data/staging/pending/chg_test_002.json

  # Approve via Paperclip webhook
  curl -s -X POST http://localhost:3100/webhooks/approval \
    -H "Content-Type: application/json" \
    -H "X-API-Key: dev-paperclip-key" \
    -d '{
      "proposal_id": "chg_test_002",
      "decision": "approved",
      "reviewer": "test-hod@brooker.co.th",
      "timestamp": "2026-04-08T10:30:00Z"
    }' | jq .
  ```

- [ ] **5.3** Check wiki-compiler received the event:
  ```bash
  docker compose logs wiki-compiler --tail 10 | grep "wiki_compile\|compiled"
  ```
  Expected: Compile event received and processed

- [ ] **5.4** Verify new decision article was auto-generated:
  ```bash
  ls -la obsidian-vault/cac/decisions/ | grep "test_002\|liquidity"
  ```

---

## Phase 6: Lint Endpoint

- [ ] **6.1** Run lint on CAC department:
  ```bash
  curl -s -X POST http://localhost:3007/lint \
    -H "Content-Type: application/json" \
    -d '{"dept_id": "cac"}' | jq .
  ```
  Expected: LintReport with `articles_scanned`, `issues_found`, `results` array

- [ ] **6.2** Verify lint-report.md was written:
  ```bash
  cat obsidian-vault/cac/lint-report.md | head -20
  ```
  Expected: Formatted lint report with severity sections

---

## Phase 7: Paperclip DB Seed — Maintenance Agent

- [ ] **7.1** Register wiki-maintenance-agent in Paperclip:
  ```bash
  curl -s -X POST http://localhost:3100/agents/register \
    -H "Content-Type: application/json" \
    -H "X-API-Key: dev-paperclip-key" \
    -d '{
      "agent_name": "wiki-maintenance-agent",
      "department": "shared",
      "agent_role": "worker",
      "skills": ["wiki-maintenance"],
      "data_scope": {"vault_access": "all_departments"},
      "permissions": {"can_archive": true, "can_write_vault": true}
    }' | jq .
  ```
  Expected: 200 OK with agent registration confirmation

- [ ] **7.2** Verify heartbeat endpoint:
  ```bash
  curl -s -X POST http://localhost:3100/heartbeat \
    -H "Content-Type: application/json" \
    -H "X-API-Key: dev-paperclip-key" \
    -d '{
      "agent_name": "wiki-maintenance-agent",
      "department": "shared",
      "agent_role": "worker"
    }' | jq .
  ```
  Expected: Heartbeat acknowledged

---

## Phase 8: RAG Ingestion → Wiki Compiler Wiring

- [ ] **8.1** Verify WIKI_COMPILER_URL is set in rag-ingestion:
  ```bash
  docker compose exec rag-ingestion env | grep WIKI_COMPILER
  ```
  Expected: `WIKI_COMPILER_URL=http://wiki-compiler:3007`

- [ ] **8.2** Upload a test document through rag-ingestion:
  ```bash
  curl -s -X POST http://localhost:3004/ingest/document \
    -F "file=@test-document.pdf" \
    -F "dept=CAC" \
    -F "doc_type=pdf" \
    -F "collection=cac_docs" | jq .
  ```

- [ ] **8.3** Check wiki-compiler logs for document_ingested event:
  ```bash
  docker compose logs wiki-compiler --tail 10 | grep "document_ingested"
  ```
  Expected: Compile event received for the document

---

## Phase 9: E2E Golden Path

Test the complete flow: proposal → approval → wiki article → Qdrant → agent query

- [ ] **9.1** Create a staging proposal:
  ```bash
  echo '{"id":"chg_e2e_001","agent":"capital-agent","file":"ALCO_Tracker.xlsx","tab":"Capital","cell":"D8","old_value":"13.2","new_value":"13.8","source":"Slack #cac-committee | Jane | 2026-04-08","confidence":0.92,"reasoning":"CAR improved after Q1 earnings","status":"pending"}' > data/staging/pending/chg_e2e_001.json
  ```

- [ ] **9.2** Approve via Paperclip webhook
- [ ] **9.3** Wait 15 seconds (wiki compilation + VaultWatcher debounce + embedding)
- [ ] **9.4** Query the CAC orchestrator asking about the capital adequacy change:
  ```bash
  # Via Slack bot or direct API
  curl -s -X POST http://localhost:3001/query \
    -H "Content-Type: application/json" \
    -d '{"query": "What was the recent change to capital adequacy ratio?", "user_id": "test", "channel": "test"}' | jq .
  ```
  Expected: Response cites the wiki decision article as a source

---

## Phase 10: Cleanup & Final Verification

- [ ] **10.1** Remove test staging proposals:
  ```bash
  rm -f data/staging/pending/chg_test_*.json data/staging/pending/chg_e2e_*.json
  rm -f data/staging/approved/chg_test_*.json data/staging/approved/chg_e2e_*.json
  ```

- [ ] **10.2** Verify all 13+ services are healthy:
  ```bash
  for port in 3000 3001 3003 3004 3005 3006 3007 3100 4000; do
    echo -n "Port $port: "
    curl -s http://localhost:$port/health | jq -r '.status // .service // "no response"' 2>/dev/null || echo "unreachable"
  done
  ```

- [ ] **10.3** Check docker compose ps — all services should be "running":
  ```bash
  docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
  ```

- [ ] **10.4** Update Implementation.md — mark remaining Stage 9 deferred items complete

---

## Troubleshooting

### Can't reach DGX Spark LLM from Docker containers
```bash
# Test from inside a container:
docker compose exec wiki-compiler curl -s http://host.docker.internal:8000/v1/models

# If it fails:
# 1. Check extra_hosts mapping in docker-compose.yml
#    Should be: - "host.docker.internal:<DGX_SPARK_IP>"
# 2. Check DGX Spark firewall allows inbound on 8000/8002
# 3. Test from Windows host first: curl http://<DGX_SPARK_IP>:8000/v1/models
# 4. If using .env: verify DGX_SPARK_IP is set and docker-compose.yml uses ${DGX_SPARK_IP}
```

### wiki-compiler won't start
```bash
docker compose logs wiki-compiler --tail 50
# Common issues:
# - wiki_schema.json not found → check volume mount: ./config:/app/config:ro
# - vLLM unreachable → verify host.docker.internal resolves to DGX Spark IP (see above)
# - Port conflict → check nothing else is on 3007
# - Python deps missing → rebuild: docker compose build --no-cache wiki-compiler
```

### VaultWatcher doesn't pick up new articles
```bash
docker compose logs rag-ingestion --tail 50 | grep vault
# Common issues:
# - obsidian_watch.json not loaded → check OBSIDIAN_WATCH_CONFIG env var
# - Wrong collection → check watch_folders path prefix matching
# - File ignored → check ignore_folders/ignore_files in config
# - Windows path separators → VaultWatcher normalizes \\ to / but double-check
```

### Paperclip doesn't route to wiki-compiler
```bash
docker compose exec paperclip env | grep WIKI
# Common issues:
# - WIKI_COMPILER_URL not set → add to docker-compose.yml paperclip environment
# - Network isolation → both must be on agent-net
# - wiki-compiler not running → docker compose ps
```

### LLM compilation slow (> 30s)
```bash
# Check vLLM is responding from Windows host:
curl -s http://<DGX_SPARK_IP>:8000/v1/models | jq .

# Check DGX Spark GPU utilization (SSH to DGX Spark):
nvidia-smi

# Common issues:
# - Model not loaded → check vLLM logs on DGX Spark
# - Network latency → DGX Spark should be on same LAN (< 1ms RTT)
# - Concurrent requests → check if other services are also calling vLLM
# - Reduce max_tokens in wiki_schema.json for faster responses
```

### Windows-specific: Docker Desktop volume mount issues
```bash
# Docker Desktop on Windows needs shared drives configured
# Settings → Resources → File Sharing → ensure project drive is shared

# If obsidian-vault mount shows empty inside container:
docker compose exec wiki-compiler ls /mnt/obsidian-vault/
# Should show: cac/ hr/ shared/ templates/ skills/ index.md

# If empty, check docker-compose.yml volume path uses forward slashes:
# volumes:
#   - ./obsidian-vault:/mnt/obsidian-vault:rw    ← correct
#   - .\obsidian-vault:/mnt/obsidian-vault:rw    ← may fail on some Docker versions
```

### Article frontmatter invalid
```bash
# Check the raw LLM output
docker compose logs wiki-compiler --tail 50 | grep "parse_response\|frontmatter"
# The compiler falls back to constructing frontmatter from event metadata
# if the LLM doesn't return valid YAML frontmatter
```

---

## Success Criteria

All boxes checked above = Stage 9 fully deployed. The wiki-compiler is:
- Receiving events from Paperclip (approvals, escalations) and RAG ingestion (documents)
- Compiling structured wiki articles via Qwen3.5 122B
- Writing articles to department-scoped vault directories
- Auto-maintaining index.md, log.md, and [[backlinks]]
- VaultWatcher embedding articles to Qdrant for agent retrieval
- Lint endpoint detecting wiki health issues

**Next:** Stage 10 — UAT + Go-Live
