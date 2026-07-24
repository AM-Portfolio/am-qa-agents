# Local start — qa-agent

Prerequisites (from am-agents lab, usually via port-forward):

| Service | Default URL | Notes |
|---------|-------------|-------|
| Temporal **UI** (traces) | https://temporal.asrax.in | No port-forward; open in browser |
| Temporal **gRPC** (SDK) | `localhost:7233` via `kubectl -n temporal port-forward svc/temporal-frontend 7233:7233` | In-cluster: `temporal-frontend.temporal.svc.cluster.local:7233`. **Not** `temporal.asrax.in` (that is UI only) |
| LiteLLM | `localhost:4000` | LLM |
| tool-agent | `localhost:8141` | notify / document.store |
| OpenProject | `https://openproject.asrax.in` | tickets |
| Cliq webhook | in `.env` | notify |
| Postgres | `localhost:5432` | optional; sqlite used by default |
| MinIO | `localhost:9000` | PDF store when document.store enabled |

## npm scripts (preferred)

```powershell
cd F:\am-repos\am-repos\qa-agent
npm run setup          # pip install -e ".[dev,temporal]"
npm run gateway        # http://127.0.0.1:8150  (loads .env)
npm run worker         # Temporal queue qa-agent-v1
npm run start:all      # gateway + worker together
npm run health         # GET /health
npm run smoke          # POST release-readiness (inline)
npm run pilot:local    # health + CI allow/deny (am-analysis pilot)
npm run postman:sync   # push collection to Postman (needs POSTMAN_API_KEY)
npm run test
npm run release:approve -- <tracking_id>
npm run release:reject -- <tracking_id>
npm run logs:clean
```

Postman: collection **`qa-agent-local`** (updated via Cursor Postman MCP or `npm run postman:sync`). See [PILOT_CORE_ANALYSIS.md](PILOT_CORE_ANALYSIS.md).

Aliases: `npm start` / `npm run dev` → gateway.

## Env

`.env` is gitignored (values from `am-agents/.env`). Template: `.env.example`.

## Manual (without npm)

```powershell
pip install -e ".[dev,temporal]"
am-qa-agent-gateway
am-qa-agent-worker
```

Flip skips in `.env` when specialists are up: `QA_AGENT_SKIP_UI_TEST=false`, `QA_AGENT_SKIP_FIN_AGENT=false`, `QA_AGENT_SKIP_OBSERVE=false`, `QA_AGENT_SKIP_DOCUMENT_STORE=false`.
