# am-qa-agents

## Layout

| Path | Role |
|------|------|
| [`qa-agent/`](qa-agent/) | **One backend tree** — SPT + UI evidence + release-gate |
| [`qa-portal-ui/`](qa-portal-ui/) | Flutter operator portal |
| [`bkp/`](bkp/) | Legacy backup only — no production dependency |

See [`docs/UNIFIED_LAYOUT.md`](docs/UNIFIED_LAYOUT.md).

## Local

```powershell
cd am-qa-agents
pip install -e ".[all]"
$env:PYTHONPATH = "$(Get-Location)\qa-agent"
$env:QA_AGENT_WORKER_ENABLED = "0"
python -m composition.main   # :8150
```
