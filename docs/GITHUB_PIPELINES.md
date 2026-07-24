# GitHub pipelines (am-qa-agents monorepo)

Canonical repo: https://github.com/AM-Portfolio/am-qa-agents

| Package / path | Workflow file | Display name | Image (unchanged) |
|----------------|---------------|--------------|-------------------|
| `qa-backend/api-load/**`, `qa-portal-ui/**` (HTML) | `api-load.yml` | Publish — api-load (+ qa-portal-ui) | `am-spt-poc` |
| manual | `deploy-api-load.yml` | Deploy — api-load | `am-spt-poc` |
| `qa-backend/ui-evidence/**` | `ui-evidence.yml` | Publish — ui-evidence | `am-ui-test-agent` |
| manual | `deploy-ui-evidence.yml` | Deploy — ui-evidence | `am-ui-test-agent` |
| `qa-backend/release-gate/**` | `release-gate.yml` | Publish — release-gate | `am-qa-agent` |
| manual | `deploy-release-gate.yml` | Deploy — release-gate | `am-qa-agent` |
| `qa-portal-ui/**` (Flutter) | `qa-portal-ui.yml` | Publish — qa-portal-ui | web artifact (`am-modern-ui` checkout for design system) |

Legacy trees under `am-agents` / standalone `qa-agent` are deprecated — see `MOVED.md` there.
