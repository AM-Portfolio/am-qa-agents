# Pre-Release Gate — TODOS

Track in order. Do not start P2 until P0 exit criteria pass.  
Mark `[x]` only after [VERIFICATION.md](./VERIFICATION.md) MCP rows for that phase pass.

## Pre-P0 blockers

- [x] `/qa` and `/ui-test` return **JSON** health on **prod** (`am.asrax.in`) — hotfixed `init_db` in pod 2026-10-05
- [ ] Dig (`am-dev`) still SPA / no Endpoints — awaiting image `p0-a2baa8e` deploy
- [ ] Ship image with lifespan `init_db` + `ops/start` — PR [#2](https://github.com/AM-Portfolio/am-qa-agents/pull/2); docker build in progress
- [ ] Temporal worker on Contabo `default` — gitops PR [#86](https://github.com/AM-Portfolio/am-gitops/pull/86) (needs human merge + Contabo sync)
- [x] `QA_AGENT_GATEWAY_TOKEN` in Vault (prod/dev modules) + `am-modern-ui` GHA secret set
- [x] Thin GHA PR — [#168](https://github.com/AM-Portfolio/am-modern-ui/pull/168)

## P0 — Thin GHA → Temporal + prod_ui_full

- [x] Rewrite `am-modern-ui/.github/workflows/ui-test-gate.yml` (fail-closed; no cluster DNS; no SKIPPED green; no in-GHA Playwright)
- [x] `wait_deploy_healthy` + agent health; run `prod_ui_full`; progress record
- [x] Extend `GET /qa/v2/releases/{id}` with `phase`, `pending[]`, `blockers[]`, `ui_pct`
- [ ] GitHub check-run streaming from watch job / agent (step summary + poll in P0; full check-run API next)
- [ ] Complete P0 table in VERIFICATION.md (needs live JSON health + Temporal ns)

**P0 exit:** `workflow_dispatch` `deploy_mode=none` → Temporal phases visible → clear green or clear red.

## P1 — Grafana + latency + SPT

- [ ] `grafana_evidence_t0` / `t1` activities + pack JSON
- [ ] Latency baseline formula (`[now-2h,now-1h]` vs `[now-15m,now]`; regress 1.5× and +200ms)
- [ ] SPT profiles: `market-top-movers`, `market-fno-list`, `market-ipo-list`, paper portfolio/orders
- [ ] Scorecard / Drive rows for health + latency + SPT run ids
- [ ] Complete P1 table in VERIFICATION.md

## P2 — pre_release_full

- [ ] Register suite `pre_release_full` in `registry.py`
- [ ] `AUTH_GOOGLE_FLOW` (storage-state soft if missing)
- [ ] `BASKET_CREATE_FLOW` + cleanup
- [ ] `TRADE_PAPER_ORDER_FLOW` (paper guard)
- [ ] `MARKET_DEPTH_FLOW` (movers/F&O/IPO/analysis; market-hours soft)
- [ ] `AI_CHAT_QUERY_FLOW` (AI-capable test user)
- [ ] `assert_market_data_populated` helper + unit fixtures
- [ ] Complete P2 table in VERIFICATION.md

## P3 — Deploy modes

- [ ] `deploy_mode=image_tag` Contabo pin + Environment Approve wait
- [ ] `deploy_mode=branch` build/publish then pin
- [ ] Document Approve wait in UI_TEST_GATE.md
- [ ] Complete P3 table in VERIFICATION.md

## Docs

- [ ] Keep this pack current: PLAN / TODOS / VERIFICATION / architecture.drawio
- [ ] Operator doc `am-modern-ui/docs/UI_TEST_GATE.md`
- [ ] Update `RELEASE_REPORT.md` phase order
- [ ] P0 proof run linked (Actions URL + Temporal workflow id)
