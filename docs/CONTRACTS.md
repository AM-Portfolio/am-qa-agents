# External contracts — must stay green after one-pod cutover

| Caller | Contract | Status |
|--------|----------|--------|
| Flutter portal | `API_BASE` → `/spt-poc` (`ROOT_PATH`, `base-href=/spt-poc/ui/`) | Preserve Traefik |
| Portal UI-test facade | `/api/ui-test/*` on SPT | Same SPT routes |
| Public UI agent | `https://{host}/ui-test` + `/api/v1/test/*` | Second IngressRoute → same Service |
| am-core-services notify | `QA_AGENT_BASE_URL` + `/v2/workflows/release-readiness` | Point at same Service |
| Control MCP | `/mcp` + `spt_*` tools under `/spt-poc` | Mounted from SPT |
| GitHub webhook | `POST /webhooks/github` | Release routes on unified app |
| HITL | `/v2/runs/{id}`, signals, `/v2/learning/promote` | Same |
| Health | `/health`, `/ready`, `/unified/health` | Unified pod |

## In-pod defaults

- `SPT_UI_TEST_AGENT_URL` / `UI_TEST_AGENT_BASE_URL` = `http://127.0.0.1:8150`
- Temporal worker started by `composition.main` (same container)

## Layout

All live backend packages live under [`qa-agent/`](../qa-agent/) (`spt/`, `ui_evidence/`, `gateway/`, `orchestrator/`, `composition/`, …).
