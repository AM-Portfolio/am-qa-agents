# GitHub pipelines (am-qa-agents monorepo)

Canonical repo: https://github.com/AM-Portfolio/am-qa-agents

| Package / path | Workflow file | Display name | Image |
|----------------|---------------|--------------|-------|
| `qa-agent/**`, `qa-portal-ui/**`, `pyproject.toml` | `qa-agent.yml` | Publish — qa-agent | `am-qa-agents` |
| manual | `deploy-qa-agent.yml` | Deploy — qa-agent | `am-qa-agents` |
| `qa-portal-ui/**` (Flutter) | `qa-portal-ui.yml` | Publish — qa-portal-ui | web artifact |

Old per-module workflows (`api-load`, `ui-evidence`, `release-gate`) were removed with the `qa-backend/` tree.
