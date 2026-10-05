# Pre-Release Gate — VERIFICATION (phase × use-case × MCP × corners)

**Pack:** [PLAN.md](./PLAN.md) · [TODOS.md](./TODOS.md) · [architecture.drawio](./architecture.drawio)

**Orchestration lock:** GHA starts Temporal only; Temporal owns suites.  
**MCP:** `user-am-qa-agent`, `user-temporal`, `user-grafana`, `user-argocd-prod`.  
**Before MCP:** `AM_AGENT_ENV=prod` (or `dev`) → `am ai mcp-sync --ide cursor`.

---

## Baseline MCP snapshot (2026-10-05)

| Check | Result | Implication |
|-------|--------|-------------|
| `qa_portal_urls` | env=`dev` → `am-dev.asrax.in` | Sync to **prod** for prod gate proof |
| `spt_health` / `ui_test_health` | 200 + **SPA HTML** (until Endpoints empty) | Must assert **JSON**, not status alone |
| `ui_test_list_profiles` | SPA HTML | Profiles API not on dig path yet |
| Temporal `AsraxReleaseOpsWorkflow` | Namespace `qa-agent` **not found** | Contabo overlay uses `TEMPORAL_NAMESPACE=default` |

### Live prod restore (2026-10-05 ~16:46 UTC)

| Check | Result |
|-------|--------|
| Root cause | FastAPI `lifespan` skipped `@app.on_event("startup")` → `init_db()` never ran → `relation "runs" does not exist` → startup probe **500** → no Endpoints → Traefik fell through to modern-ui SPA |
| Hotfix | Ran `init_db()` in prod pod → tables created |
| `https://am.asrax.in/qa/health` | **`application/json`** `status=ok` |
| Code fix (unshipped) | Move seed/`init_db` into lifespan; probe-safe `health()` |

**Pre-P0 corner:** Ship lifespan fix image; dig Endpoints; Temporal `default` + worker; then P0 dispatch.

---

## P0 — Thin GHA → Temporal + `prod_ui_full`

| # | Use case | Verify | MCP / tool | Pass |
|---|----------|--------|------------|------|
| P0.1 | Fail-closed (no skip) | Bad token / unreachable → job **fails** | Dispatch Actions | |
| P0.2 | Health = JSON | Body parses as JSON ok/status | `spt_health`, `spt_ready`, `ui_test_health` | |
| P0.3 | Profiles listed | AUTH_*, PORTFOLIO_*, suite names | `ui_test_list_profiles` | |
| P0.4 | Temporal started | Running workflow | `list_workflows` / `describe_workflow` | |
| P0.5 | First-check | `pending[]` accurate | Progress API + Grafana `query_prometheus` | |
| P0.6 | `prod_ui_full` | Traces / ui_pct | Progress + Trace Viewer | |
| P0.7 | Check-runs | Phase names in GH | Actions UI | |
| P0.8 | Progress API | `phase,status,services,pending,blockers` | `GET /qa/v2/releases/{id}` | |

**P0 corners:** SPA HTML→fail · missing Temporal ns→actionable error · bad token→401 · unhealthy pods→no suite · GHA cancel≠kill Temporal · duplicate dispatch idempotent/reject.

**P0 exit:** `deploy_mode=none` → clear green **or** clear red; never SKIPPED.

---

## P1 — Grafana + latency + SPT

| # | Use case | Verify | MCP / tool | Pass |
|---|----------|--------|------------|------|
| P1.1 | Release Glance | Dashboard exists | `search_dashboards` / `get_dashboard_by_uid` `release-glance` | |
| P1.2 | Pod health | Ready % for `am-apps-prod` | `query_prometheus` | |
| P1.3 | Latency compare | baseline vs post in JSON | `query_prometheus` + pack | |
| P1.4 | Regress gate | 1.5× and +200ms | Fixture / flag | |
| P1.5–8 | SPT data | movers / F&O / IPO / paper orders | `spt_list_profiles`, `spt_execute_run`, `spt_get_run_live` | |
| P1.9 | Scorecard | Health + latency + run ids | Sheet/Drive open | |
| P1.10 | Parallel legs | UI∥API in progress | Progress API | |

**P1 corners:** Market closed→soft movers · Grafana auth fail→closed · empty baseline→fallback · compare only after suites.

---

## P2 — `pre_release_full`

| # | Use case | Verify | MCP / tool | Pass |
|---|----------|--------|------------|------|
| P2.1 | Suite registered | Name present | `ui_test_list_profiles` | |
| P2.2 | Credentials login | Trace | UI suite | |
| P2.3 | Google storage-state | Soft if missing | Vault + profile | |
| P2.4 | Basket create/cleanup | Appears then removed | UI suite | |
| P2.5 | Paper Add Trade | Order listed; not live | UI suite | |
| P2.6 | Market depth | Gainers/F&O/IPO/analysis | UI + SPT | |
| P2.7 | AI chat query | Non-empty reply | UI suite | |
| P2.8 | Default suite | ops start `pre_release_full` | Gateway body | |
| P2.9 | No-zero-data | Unit + live hours rules | pytest + suite | |

**P2 corners:** No Google secret→soft · no AI entitlement→clear fail · null portfolio_id→skip deep link · live portfolio→block · empty IPO→empty-state OK · session zeros→hard / overnight soft.

---

## P3 — Deploy modes

| # | Use case | Verify | MCP / tool | Pass |
|---|----------|--------|------------|------|
| P3.1 | `deploy_mode=none` | No Contabo job | Actions | |
| P3.2 | `image_tag` | Pin + Approve | Argo `get_application` | |
| P3.3 | `branch` | Build→pin→Temporal | Actions + Temporal | |
| P3.4 | Approve wait | Job `waiting` then continues | Actions Environments | |
| P3.5 | Bad tag | First-check fail | Actions + progress | |

**P3 corners:** Approve denied→clear fail · wrong ns→health fail · race deploy→probe backoff then fail.

---

## Cross-cutting MCP script (end of each phase)

1. `qa_portal_urls` — env correct  
2. `spt_health` + `spt_ready` — **JSON**  
3. `ui_test_health` — **JSON**  
4. `ui_test_list_profiles`  
5. `spt_list_profiles` (P1+)  
6. Temporal `list_workflows` / `describe_workflow`  
7. Grafana `search_dashboards` + `query_prometheus`  
8. Write SPT only via Temporal/gateway (not casual Cursor write)  
9. Progress API — pending empty when complete  

---

## Global corner matrix

| Corner | Expected |
|--------|----------|
| SPA HTML on /qa or /ui-test | Fail health |
| Temporal ns missing | Fail start + hint |
| Missing gateway token | Fail GHA start |
| Unhealthy pods | No Playwright/SPT |
| Market closed | Soft zero-data |
| Dual GHA+local suite | Forbidden |
| GHA cancelled | Temporal continues; re-poll `tracking_id` |
| Latency no series | Fallback + caveat |
