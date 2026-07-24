# Pilot: am-core-services / am-analysis opt-in

Release-readiness from CI is **opt-in** via a service manifest (same idea as `observability.yaml`).

## What is wired

| Piece | Location |
|-------|----------|
| Service manifest | `am-core-services/services/am-analysis/qa-agent.yaml` (`environment: dev`) |
| CI notify | `am-core-services/.github/workflows/qa-agent-notify.yml` (paths: `services/am-analysis/**`) |
| Gateway allowlist | `qa-agent/config/trigger-policy.yaml` |
| SPT playbooks | `catalog/spt/release-gate.yaml` + `smoke-default.yaml` → `repos: [am-core-services]` |

## GitHub secrets (am-core-services)

- `QA_AGENT_BASE_URL` — gateway base URL
- `QA_AGENT_GATEWAY_TOKEN` — Bearer token

## Postman (agent-updatable)

Cursor has **Postman MCP** (`postman` in `~/.cursor/mcp.json`, full mode). After MCP reload, ask Cursor to update the Postman collection — no copy-paste.

| Resource | Name / location |
|----------|------------------|
| Workspace | **Asrax** |
| Collection | `qa-agent-local` |
| Environment | `qa-agent-local` (`baseUrl=http://127.0.0.1:8150`, `token`) |

Requests: health, allow `am-analysis`, deny `am-gateway`, HITL approve/reject.

Re-sync from repo (needs `POSTMAN_API_KEY` in shell env — do not commit the key):

```powershell
$env:POSTMAN_API_KEY="…"
npm run postman:sync
```

## Local verify

```powershell
cd qa-agent
npm run setup
# Temporal gRPC (UI is temporal.asrax.in — not usable as TEMPORAL_HOST):
kubectl -n temporal port-forward svc/temporal-frontend 7233:7233
npm run gateway          # terminal 1
npm run worker           # terminal 2 — namespace qa-agent / queue qa-agent-release-v1
npm run pilot:local      # use_temporal=true by default
# inline fallback: $env:QA_AGENT_USE_TEMPORAL="false"; npm run pilot:local
```

Expect allow → `mode: temporal` + Temporal UI link; deny → `"skipped": true`.
Pilot auto-approves HITL so the workflow can finish while you watch steps in Temporal.

```bash
npm test -- tests/test_trigger_policy.py
```

## Watch E2E traces

| What | Where |
|------|--------|
| Temporal workflow / activities | https://temporal.asrax.in (namespace **`qa-agent`**, queue **`qa-agent-release-v1`**) |
| Temporal MCP (Cursor) | `~/.cursor/mcp.json` → server **`temporal`** (`@alisaitteke/temporal-mcp`, `TEMPORAL_TOOLS=all`) via HTTPS UI API — list/describe/history/signal/start/cancel/… |
| Gateway logs | terminal running `npm run gateway` / `npm run worker` |
| HITL / tracking | response `tracking_id` + `workflow_id` |

**Important:** `TEMPORAL_HOST` for the Python SDK must be **gRPC** (`localhost:7233` after port-forward, or in-cluster DNS). Setting it to `temporal.asrax.in` will not work — that hostname is only the Web UI.

To avoid port-forward for the SDK, run gateway+worker **in the cluster** (Helm) so they use `temporal-frontend.temporal.svc.cluster.local:7233`. Exposing Temporal frontend on the public internet is not configured today (security).

