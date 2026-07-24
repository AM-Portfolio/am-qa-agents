# qa-agent

**Canonical agent name:** `qa-agent`  
**Path:** standalone repo (sibling of `am-agents`, `am-fin-agent`)

Commit-driven **release readiness** orchestrator (Phases 0–4 implemented).

| Specialist | Repo |
|------------|------|
| Pattern reference | [am-agents/support-agent](../am-agents/support-agent/) |
| UI smoke | [am-agents/ui-test-agent](../am-agents/ui-test-agent/) |
| Notify / work-item | [am-agents/tool-agent](../am-agents/tool-agent/) |
| Data prep | [am-fin-agent](../am-fin-agent/) |
| GitNexus index Jobs | [am-scripts/code-intelligence](../am-scripts/code-intelligence/) — **not owned by qa-agent** |

## Phase status

| Phase | Status |
|-------|--------|
| **0 — MVP** | **Done** — webhook, classify, smoke ui-test, notify |
| **1 — Index await + LoadContext + fin-agent** | **Done** |
| **2 — Verify + comparison + PDF** | **Done** |
| **3 — Full matrix** | **Done** — ranker, ChangeIntent, ticket handoff, episodes |
| **4 — Release gate** | **Done** — HITL, learning, SAST-first |

Design: [docs/QA_AGENT_PLAN.md](docs/QA_AGENT_PLAN.md) · Draw.io: [docs/qa-agent.drawio](docs/qa-agent.drawio) · Ranker: [docs/MATRIX_RANKER.md](docs/MATRIX_RANKER.md) · ADRs: [docs/decisions/](docs/decisions/) · Remaining env wiring: [docs/BACKLOG.md](docs/BACKLOG.md) · Pilot (core / am-analysis): [docs/PILOT_CORE_ANALYSIS.md](docs/PILOT_CORE_ANALYSIS.md)

## Deploy

```bash
# Helm (see deploy/helm/README.md)
helm upgrade --install qa-agent ./deploy/helm -n am-ai
```

## Run locally

See **[docs/LOCAL_RUN.md](docs/LOCAL_RUN.md)**. Env: **`.env`** (gitignored). Template: `.env.example`.

```bash
cd qa-agent
npm run setup          # pip install -e ".[dev,temporal]"
npm run gateway        # → http://127.0.0.1:8150/health
# other terminal:
npm run worker         # optional Temporal
npm run smoke          # POST release-readiness inline
npm test
```

| Script | What it does |
|--------|----------------|
| `npm run setup` | Install Python package + temporal/dev extras |
| `npm run gateway` / `start` / `dev` | Gateway API (port 8150) |
| `npm run worker` | Temporal worker (`qa-agent` / `qa-agent-release-v1`) |
| `npm run start:all` | Gateway + worker together |
| `npm run health` | Health check |
| `npm run smoke` | Inline release-readiness smoke |
| `npm run release:approve -- <id>` | HITL `approve.release` |
| `npm run release:reject -- <id>` | HITL `reject.release` |
| `npm test` | pytest |
| `npm run logs:clean` | Clear `artifacts/` |

### qa-route flow (Phases 1–4)

`classify` → `resolve_load` → `await_index` → **`security_scan`** → `change_intent` → `build_test_matrix` → `fin_data_prep` → `execute_matrix` → `collect_comparisons` → `post_test_verify` → `analyze` → `publish_pdf` → **`await HITL`** → `persist_episode` → `evaluate_learning` → `notify`

Dev-route: `classify` → `dev_handoff_ticket` → `persist_episode` → `notify`

### HITL signals

```bash
# After run reaches awaiting_release (or inline auto):
curl -s -X POST http://127.0.0.1:8150/v2/runs/{tracking_id}/signals/approve.release ^
  -H "Authorization: Bearer dev-token-change-me" ^
  -H "Content-Type: application/json" ^
  -d "{\"actor\":\"you\",\"notes\":\"looks good\"}"
```

### Manual start

```bash
curl -s -X POST http://127.0.0.1:8150/v2/workflows/release-readiness ^
  -H "Authorization: Bearer dev-token-change-me" ^
  -H "Content-Type: application/json" ^
  -d "{\"repo\":\"am/am-market\",\"branch\":\"feature/x\",\"head_sha\":\"abc123\",\"ci_conclusion\":\"success\",\"use_temporal\":false}"
```

### Tests

```bash
pytest -q
```

## Queue

Temporal: namespace **`qa-agent`**, task queue **`qa-agent-release-v1`** (env `TEMPORAL_NAMESPACE` / `TEMPORAL_TASK_QUEUE`). Not shared with support-agent (`default` / `support-agent-v2`).
