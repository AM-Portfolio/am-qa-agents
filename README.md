# am-qa-agents

## Layout

| Path | Role |
|------|------|
| [`qa-agent/`](qa-agent/) | **One backend tree** — SPT + UI evidence + release-gate |
| [`qa-portal-ui/`](qa-portal-ui/) | Flutter operator portal |

See [`docs/UNIFIED_LAYOUT.md`](docs/UNIFIED_LAYOUT.md) and [`docs/CONTRACTS.md`](docs/CONTRACTS.md).

## Local

```powershell
cd am-qa-agents
pip install -e ".[all]"
$env:PYTHONPATH = "$(Get-Location)\qa-agent"
$env:QA_AGENT_WORKER_ENABLED = "0"
python -m composition.main   # :8150
```

## Deploy

Image from [`qa-agent/Dockerfile`](qa-agent/Dockerfile); chart in [`qa-agent/helm/`](qa-agent/helm/). CI: `.github/workflows/qa-agent.yml`.
