# Service onboard prep (Temporal)

When a service catalog is ready (or an operator triggers Specs), **ServiceOnboardPrepWorkflow** prepares Specs end-to-end and returns a structured `steps[]` report so dig/dev failures show **which phase** failed — not a single opaque 500.

## Queue / worker

- Same family as release readiness: `qa-agent-release-v1` (env overlay `qa-agent-release-dev-v1`)
- Workflow name: `ServiceOnboardPrepWorkflow`
- Activities: `activity_onboard_*` in `qa-agent/release_gate/orchestrator/activities/onboard_prep.py`

## Phases (ordered)

| Step | Required | Notes |
|------|----------|--------|
| `analyze` | yes | Registration + reachable target |
| `openapi_sync` | yes | Live OpenAPI pull (`force=True`) |
| `apis_catalog` | yes | Fail if `health-fallback` only |
| `tools_refresh` | yes | Build tools + APIs↔tools parity |
| `contract` | yes | Plugin `min_tools` if plugin exists; else parity |
| `auth_try_token` | yes | Platform JWT for env (`dig` → `dev`) |
| `prepare_mcp` | soft | Warn if `mapped_count=0` |
| `generate_all_payloads` | yes to start | Per-API soft unless `strict_payloads` |
| `llm_fallback` | soft | LiteLLM / flag status |
| `tools_smoke` | soft\* | Health + one GET; \*auth hard |
| `overview_report` | soft | Attach warnings |

### Smoke classification

- **Hard** (`auth_jwks_mismatch`, `identity_unavailable`): JWT / JWKS / identity failures stop the workflow (`ok: false`).
- **Soft** (`billing_dependency`): `LAGO_API_ERROR` / business `NOT_FOUND` — warning only (dig Lago gap).

## Triggers

1. **HTTP**  
   - `POST /api/services/{service}/onboard`  
   - `POST /v2/workflows/service-onboard` (gateway token)  
   Body: `{ "environment": "dev", "allow_llm": true, "strict_payloads": false, "wait": false }`

2. **MCP**  
   - `spt_onboard_service(service, environment="dev", …)`  
   - Poll: `spt_onboard_status(workflow_id)`

3. **CI** (`am-core-services` `qa-agent-notify`): after release-readiness notify, fire-and-forget onboard start.

4. **Portal**: Specs Config row → **Onboard prep** (polls until `steps[]` ready).

Inline fallback: if Temporal is down, the same activities run in-process (`mode: inline` / `inline_fallback`).

## Report shape

```json
{
  "ok": false,
  "failed_step": "openapi_sync",
  "service": "am-subscription",
  "environment": "dev",
  "workflow_id": "service-onboard-…",
  "warnings": ["tools_smoke:billing_dependency"],
  "steps": [
    {
      "step": "openapi_sync",
      "ok": false,
      "status": "openapi_unavailable",
      "error": "short message",
      "evidence": { "openapi_url": "…", "http_status": 502 },
      "duration_ms": 1234,
      "required": true,
      "hard_fail": true
    }
  ]
}
```

Persisted at `{data_dir}/onboard/{service}/{env}/latest.json`.  
Poll: `GET /api/services/{service}/onboard/{workflow_id}` or `…/onboard/latest`.

## Operator tip

Temporal UI: first failed activity name ≈ `failed_step`. Specs/MCP poll is enough for dig debugging without opening Temporal.
