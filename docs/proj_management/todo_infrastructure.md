# TODO — Infrastructure

Docker, data directories, networking, and deployment scripts.

---

## P0 — Critical

### [ ] Create host data directories
- Run `scripts/setup-data-dirs.sh` on the deployment host
- Creates `/data/mirror/`, `/data/staging/pending/`, `/data/staging/approved/`, `/data/staging/rejected/`, `/data/archive/`
- Without these, Docker bind-mounts fail and no service starts
- **Owner:** DevOps / whoever provisions the DGX Spark host

### [ ] Add gateway `DATABASE_URL` to docker-compose.yml
- **Audit finding (API-7 / FE-2)** — all gateway API routes crash
- `docker-compose.yml:111-135` — gateway service has no `DATABASE_URL` environment variable
- `services/gateway/src/main.py:24` reads `os.getenv("DATABASE_URL")` — skips pool creation if absent
- Every `/api/proposals`, `/api/escalations`, `/api/analytics` request crashes with AttributeError
- **Fix:** Add `DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}` to gateway environment
- **File:** `docker-compose.yml`

### [ ] Fix `NEXT_PUBLIC_GATEWAY_URL` in docker-compose.yml
- **Audit finding (FE-1)** — entire approval-ui non-functional
- `docker-compose.yml:303` sets `http://localhost:3000` — browser can't reach gateway container
- **Fix:** Set to externally accessible URL (e.g., `http://<host-ip>:8080` via nginx proxy)
- **File:** `docker-compose.yml`

### [ ] Verify Docker Compose service startup order
- Run `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` in dev mode
- Confirm all services reach `healthy` state
- Known issue: nginx healthcheck hits vLLM — if vLLM isn't running, nginx blocks dependent services
- **Workaround:** Use `docker-compose.dev.yml` override which relaxes nginx healthcheck

---

## P1 — High

### [ ] Add `sync-mirror` service to docker-compose.yml
- **Status:** [x] Done (added in previous session)
- Service definition with build context, env vars, volume mounts, healthcheck
- `mirror_data:/data/mirror:rw` (only service with write access)

### [ ] Verify volume mount permissions
- `mirror_data` must be `:ro` for all services except `sync-mirror`
- `staging_data` must be `:rw` for `cac-orchestrator`, `sync-back`, `approval-ui`
- `archive_data` must be `:rw` for `sync-back`
- Run `docker inspect <container>` on each to verify mount flags

### [ ] Nginx vLLM load-balancer configuration
- **Status:** [x] Verified correct (only port 8000, no 8001)

---

## P2 — Medium

### [ ] Run `scripts/healthcheck.sh` end-to-end
- **Status:** [x] Updated to cover all 8 HTTP services
- Verify it reports failures clearly when services are down

### [ ] Document DGX Spark deployment procedure
- Network configuration (bridge mode, port forwarding)
- GPU allocation for vLLM processes
- Systemd service files or tmux scripts for vLLM persistence
- Firewall rules for inter-container + host communication
- **Output:** `docs/deployment-guide.md` or similar

---
*Last updated: 2026-04-10*
