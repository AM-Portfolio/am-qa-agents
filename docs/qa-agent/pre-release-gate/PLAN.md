# Pre-Release Gate — PLAN

**Pack:** `docs/qa-agent/pre-release-gate/`  
**Cursor plan:** `.cursor/plans/prod_ui_test_gate_9ef83d74.plan.md`  
**Status:** Ready for phased implement (P0 first)

## Goal

Replace skip-theater `ui-test-gate.yml` with a **Temporal-orchestrated** prod release gate: first-check (pods + Grafana) → Playwright + SPT data suites → latency comparison → release Scorecard/Cliq. GitHub Actions only **starts and watches**.

## Locked decisions

| Topic | Lock |
|-------|------|
| Orchestration | Temporal `AsraxReleaseOpsWorkflow` only for suites/latency/pack |
| GHA | Thin: optional Contabo deploy → health probe → `POST /qa/v2/releases/ops/start` → poll progress |
| Target | `https://am.asrax.in` |
| Agent / SPT | `https://am.asrax.in/ui-test` and `/qa` (JSON health required) |
| P0 suite | `prod_ui_full` |
| P2+ suite | `pre_release_full` (+ Google storage-state, paper trade/basket, AI chat, market depth) |
| Mutations | Paper portfolio only |
| Dual tracker | Forbidden |

## Architecture (summary)

```
Operator → ui-test-gate.yml → [optional Contabo] → health probe
         → POST /qa/v2/releases/ops/start
         → Temporal: wait_deploy_healthy → grafana_t0
              → ui_suite ∥ api_suites → latency_compare
              → pack → soak → grafana_t1 → Sheet/Drive/Cliq
         → GHA polls GET /v2/releases/{id} → check-runs
```

See [architecture.drawio](./architecture.drawio) (Context, BusinessFlow, Containers, Sequence, DataIdentity, SecurityTrust, Failures).

## Delivery phases

| Phase | Deliverable | Exit |
|-------|-------------|------|
| **P0** | Thin GHA + Temporal first-check + `prod_ui_full` + progress API | Fail-closed dispatch; never SKIPPED green |
| **P1** | Grafana T0/T1 + latency formula + SPT movers/F&O/IPO | Scorecard shows health + p95 delta |
| **P2** | `pre_release_full` UI expansions | Paper + market depth + AI on prod user |
| **P3** | `deploy_mode=branch\|image_tag` | Tag/branch → Approve → Temporal |

## Pre-P0 blockers (MCP)

1. Dig `/qa` + `/ui-test` returning SPA HTML → treat as down until JSON health.
2. Temporal namespace `qa-agent` not found → configure before watch.

## Acceptance (DoD)

See checklist in Cursor plan + [TODOS.md](./TODOS.md). Verification steps: [VERIFICATION.md](./VERIFICATION.md).

## Out of scope

Fake preview DNS · live brokerage orders · market admin explorers · second release tracker · rebuilding Release Glance from scratch.
