# Unified layout

Python lives in **flat repo-root packages** (no `src/am_qa_agents/`):

- `composition/` — one process entry (`am-qa-agents` CLI): HTTP + Temporal worker
- `gateway/` — release-gate HTTP
- `orchestrator/` — Temporal workflows/activities
- `intelligence/`, `learning/`, `adapters/`, `stores/`, `observability/`
- `spt/` — former api-load
- `ui_evidence/` — former ui-evidence
- `common/env_urls.py` — shared URL helpers

Deploy: **one Pod, one container** (`Dockerfile` + `helm/`).

Legacy trees under `qa-backend/` are stubs pointing at the new packages.
