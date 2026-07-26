# External contracts — must stay green after one-pod cutover

| Caller | Contract | Status |
|--------|----------|--------|
| Flutter portal | `API_BASE` → `/qa` (`ROOT_PATH`, `base-href=/qa/ui/`) | Preserve Traefik |
| Portal UI-test facade | `/api/ui-test/*` on SPT | Same SPT routes |
| Public UI agent | `https://{host}/ui-test` + `/api/v1/test/*` | Second IngressRoute → same Service |
| am-core-services notify | `QA_AGENT_BASE_URL` + `/v2/workflows/release-readiness` | After catalog publish + ready poll; **SPT SoT remains `services/*/spt.yaml`** |
| Product `spt.yaml` | `am.spt/v1` ServiceLoadTest (targets, openapi) | Aggregated into ConfigMap `spt-catalog-bundle` → `/catalog-external/<service>.yaml` (any N services; Helm does not list each) |
| Product `qa-agent.yaml` | Thin CI opt-in (`spt.path` / `spt.required`) | Does **not** replace `spt.yaml` |
| am-modern-ui notify | same endpoint, `service=am-modern-ui` (UI-only, no catalog wait) | Opt-in `qa-agent.yaml` |
| am-pipelines | `notify-qa-agent.yml` `workflow_call` | Reusable POST helper |
| Control MCP | `/mcp` + `spt_*` tools under `/qa` | Mounted from SPT |
| GitHub webhook | `POST /webhooks/github` | Release routes on unified app |
| HITL | `/v2/runs/{id}`, signals, `/v2/learning/promote` | Same |
| Health | `/health`, `/ready`, `/unified/health` | Unified pod |

## In-pod defaults

- `SPT_UI_TEST_AGENT_URL` / `UI_TEST_AGENT_BASE_URL` = `http://127.0.0.1:8150`
- Temporal worker started by `composition.main` (same container)

## Layout

All live backend packages live under [`qa-agent/`](../qa-agent/) (`spt/`, `ui_evidence/`, `gateway/`, `orchestrator/`, `composition/`, …).
