# am-qa-agents

Canonical **QA agents monorepo** for AM Portfolio.

Remote: https://github.com/AM-Portfolio/am-qa-agents

## Layout (unified)

Python packages live at **repo root** (flat — no `src/am_qa_agents/`):

| Package | Role |
|---------|------|
| `composition/` | One-process entry: HTTP + Temporal worker |
| `gateway/` | Release-gate HTTP (`/v2/*`, webhooks) |
| `orchestrator/` | Temporal workflows / activities |
| `intelligence/`, `learning/`, `adapters/`, `stores/` | Release-gate domain |
| `spt/` | Former api-load (k6, catalog, MCP `/mcp`, portal APIs) |
| `ui_evidence/` | Former ui-evidence (Playwright agent) |
| `common/` | Shared `env_urls` |
| `qa-portal-ui/` | Flutter operator portal |
| `helm/` + `Dockerfile` | **One pod / one container** |

Legacy `qa-backend/*` trees are **thin stubs** only. See [`docs/UNIFIED_LAYOUT.md`](docs/UNIFIED_LAYOUT.md) and [`docs/CONTRACTS.md`](docs/CONTRACTS.md).

## Local (unified backend)

```powershell
cd am-qa-agents
pip install -e ".[all]"
$env:PYTHONPATH = (Get-Location)
$env:QA_AGENT_WORKER_ENABLED = "0"   # optional: skip Temporal locally
python -m composition.main           # http://localhost:8150
```

Flutter portal (separate):

```powershell
cd qa-portal-ui
npm run get
npm run run   # API_BASE=http://localhost:8150
```

## Deploy

One image `ghcr.io/am-portfolio/am-qa-agents`, chart in `helm/`. Traefik should route both `/spt-poc` and `/ui-test` to the same Service; notify uses `QA_AGENT_BASE_URL` → `/v2/workflows/release-readiness`.
