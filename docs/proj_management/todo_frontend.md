# TODO — Frontend (Approval UI)

Next.js approval dashboard, browser testing, and UX verification.

---

## P0 — Critical

### [ ] Fix `NEXT_PUBLIC_GATEWAY_URL` in docker-compose.yml
- **Audit finding (FE-1)** — entire dashboard non-functional in production
- `docker-compose.yml:303` sets `NEXT_PUBLIC_GATEWAY_URL=http://localhost:3000`
- `NEXT_PUBLIC_*` vars are baked into client-side JS at build time
- In browser, `localhost:3000` resolves to user's machine, not gateway container
- Every API call fails with connection refused; proposals/escalations/analytics all show "Failed to load..."
- **Fix:** Set to the externally accessible gateway URL (e.g., `http://<host-ip>:3000` or via nginx proxy at `:8080`)
- **Note:** For SSR calls (Server Components), use Docker internal hostname; for browser calls, use external URL
- **File:** `docker-compose.yml`

---

## P1 — High

### [ ] Fix `avg_confidence` null handling in StatsCards
- **Audit finding (FE-5)** — renders `NaN%` when no proposals exist
- `services/gateway/src/analytics.py:58-64` returns `"avg_confidence": null` on empty set
- `services/approval-ui/src/types/api.ts:26` types it as `number` (should be `number | null`)
- `StatsCards` does `Math.round(summary.avg_confidence * 100)` — produces `NaN%`
- **Fix:** Update type to `number | null`, add null guard in component

### [ ] Fix departments.json volume mount for standalone build
- **Audit finding (FE-3)** — config may not resolve at runtime
- `docker-compose.yml:323` mounts to `/app/src/config/departments.json:ro`
- Next.js standalone build may not resolve paths relative to original source tree
- **Fix:** Validate the mount path against the compiled standalone output, or serve config via API route

### [ ] Fix `NEXT_PUBLIC_GATEWAY_URL` build-time validation
- **Audit finding (FE-4)** — bad build silently falls back to localhost
- `services/approval-ui/src/lib/api-client.ts:14-15` — module-level constant with `|| "http://localhost:3000"` fallback
- No zod validation despite zod being a dependency
- **Fix:** Add build-time env validation (e.g., `zod` schema in `env.ts`) that fails the build if the URL is missing

### [ ] Verify approval-ui builds and runs
- Build: `docker compose build approval-ui`
- Run: `docker compose up approval-ui`
- Access: `http://localhost:4000`
- Check: page loads, proposal list renders, no console errors

### [ ] Test HOD approval workflow in browser
- **Prerequisite:** JWT keys generated, email-notifier running, gateway running, Postgres seeded
- Flow: create proposal -> email sent -> click link -> approval-ui loads -> approve/reject -> verify
- Test both approve and reject flows
- Verify department-scoped RBAC

---

## P2 — Medium

### [ ] Fix TabsContent controlled pattern in proposals page
- **Audit finding (FE-6)** — fragile under navigation
- `services/approval-ui/src/app/[dept]/proposals/page.tsx:49`
- `<TabsContent value={filter}>` binds to mutable state — semantically wrong for Tabs
- Can desync on browser back/forward or external link navigation
- **Fix:** Use static `TabsContent` per status value with conditional rendering inside

### [ ] Add auth guard for unauthenticated page access
- **Audit finding (FE-8)** — cryptic error instead of redirect
- `services/approval-ui/src/app/[dept]/proposals/[id]/page.tsx` — no auth check
- Unauthenticated user sees "Proposal not found" instead of redirect to login/error page
- `[dept]/layout.tsx` validates dept slug but not auth token
- **Fix:** Add middleware or layout-level auth check that redirects to `/approve?error=session_expired`

### [ ] Fix root page unauthenticated redirect
- **Audit finding (FE-9)** — sends unauthenticated users into broken dashboard
- `services/approval-ui/src/app/page.tsx:20` — `router.push("/cac")` when no token
- User sees all API calls fail with 401
- **Fix:** Redirect to `/approve` or a dedicated error page

### [ ] Remove `"use client"` from lib/auth.ts
- **Audit finding (FE-10)** — blocks future Server Component imports
- `services/approval-ui/src/lib/auth.ts:1` marks entire module as client boundary
- Only browser-API-using functions need client context, not the whole module
- **Fix:** Remove directive; guard browser APIs with `typeof window !== "undefined"`

### [ ] Fix departments.json containing un-interpolated shell variables
- **Audit finding (FE-11)** — literal `"${CAC_HOD_EMAIL}"` sent as email address
- `config/departments.json:19` — `hodEmails` and `slackChannels` have `"${VAR}"` syntax
- JSON does not support shell variable expansion — values are literal strings
- **Fix:** Either replace with actual values, or generate config from a template at deploy time

### [ ] Add `/api/health` endpoint to Next.js app
- **Status:** [x] Already exists at `services/approval-ui/src/app/api/health/route.ts`

### [ ] Verify Vitest frontend tests pass
- Run: `cd services/approval-ui && npm test`
- Check component rendering, mock API responses, approval button logic

### [ ] Implement Activity page
- **Audit finding (FE-12)** — currently a stub with no data
- `services/approval-ui/src/app/[dept]/activity/page.tsx` renders placeholder
- Not blocking but should be tracked

---
*Last updated: 2026-04-10*
