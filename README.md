# am-qa-agents

## Layout

| Path | Role |
|------|------|
| [`qa-agent/`](qa-agent/) | **All related backend** — SPT + release-gate (composition, gateway, orchestrator, intelligence, spt, helm, …) |
| [`ui_evidence/`](ui_evidence/) | UI Playwright agent — **kept separate** (unchanged package) |
| [`qa-portal-ui/`](qa-portal-ui/) | Flutter operator portal |
| [`bkp/`](bkp/) | Legacy backup only — **no production dependency**; safe to delete after soak |

See [`docs/UNIFIED_LAYOUT.md`](docs/UNIFIED_LAYOUT.md) and [`docs/CONTRACTS.md`](docs/CONTRACTS.md).

## Local

```powershell
cd am-qa-agents
pip install -e ".[all]"
$env:PYTHONPATH = "$(Get-Location)\qa-agent;$(Get-Location)"
$env:QA_AGENT_WORKER_ENABLED = "0"
python -m composition.main   # :8150 — SPT + release; mounts ui_evidence routes if present
```

## Deploy

One image from `qa-agent/Dockerfile` (build context = monorepo root). Chart: `qa-agent/helm/`.
