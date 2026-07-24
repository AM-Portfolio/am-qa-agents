# GitHub pipelines (am-qa-agents monorepo)

Canonical repo: https://github.com/AM-Portfolio/am-qa-agents

| Path filter | Workflow | Image |
|-------------|----------|-------|
| `qa-backend/api-load/**`, `qa-portal-ui/**` | `am-spt-poc.yml` | `am-spt-poc` |
| manual | `deploy-am-spt-poc.yml` | deploy `am-spt-poc` |
| `qa-backend/ui-evidence/**`, `docker/Dockerfile.ui-test-agent-base` | `am-ui-test-agent.yml` | `am-ui-test-agent` |
| manual | `deploy-am-ui-test-agent.yml` | deploy |
| `qa-backend/release-gate/**` | `am-qa-agent.yml` | `am-qa-agent` |
| manual | `deploy-am-qa-agent.yml` | Helm `deploy/helm` |

Legacy copies under `am-agents/poc/spt`, `am-agents/ui-test-agent`, and standalone `qa-agent` are **deprecated** — see `MOVED.md` there.
