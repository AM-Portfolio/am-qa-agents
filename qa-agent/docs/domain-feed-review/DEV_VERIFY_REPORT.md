# Contabo dig QA verify (Phase 0)

Base: `https://am-dev.asrax.in/qa`  
Date: 2026-11-08

## Health

- `/health` → **200** — `am-qa-agents`, store=db (`postgresql+psycopg`), runs_total≈33
- Latency list_10 often > SLO (expected on Contabo dig Postgres)

## Catalog / OpenAPI

- `/api/catalog` → **200**, 16 services including domain eight:
  - `am-market-data`, `am-portfolio`, `am-trade-management-service`, `am-analysis`,
    `am-parser`, `am-news`, `am-subscription`, `am-oms`
- Per-service `/api/catalog/{svc}/openapi`, `/apis`, `/target` → **200**
- Trade id is `am-trade-management-service` (not `am-trade`)

## Payload-sets (seeded this pass)

`POST /api/payload-sets/{svc}/ensure` then `GET /api/payload-sets/{svc}`:

| Service | active_version | count | label |
|---------|----------------|-------|-------|
| am-market-data | 1 | 1 | working |
| am-portfolio | 1 | 1 | working |
| am-trade-management-service | 1 | 1 | working |
| am-analysis | 1 | 1 | working |
| am-parser | 1 | 1 | working |
| am-news | 1 | 1 | working |
| am-subscription | 1 | 1 | working |
| am-oms | 1 | 1 | working |

Rows are empty (`api_count=0`) until generate/import; version records exist for Datasets inventory.

## Smoke run

- `POST /api/runs` → **405** (use execute path on this build)
- `POST /api/runs/execute` with `am-news` / dig Contabo dig → **200**, run id started (`status=running`)

## API skew vs local (`:8150`)

| Route | Contabo dig | Local |
|-------|-------------|-------|
| `/api/services/{id}/overview` | 404 | 200 |
| `/api/flows` | 404 | 200 |
| `/api/catalog/.../openapi/seed` | missing | present |
| OpenAPI path count | 87 | 134 |

Portal Contabo dig mode must soft-fail overview/flows.

## MCP

- `user-am-qa-agent` → **preprod** (`https://am-preprod.asrax.in/qa`) — health/catalog/execute OK
- `user-qa-specs-dev` — discovery/auth broken; Contabo dig verified via HTTP instead
