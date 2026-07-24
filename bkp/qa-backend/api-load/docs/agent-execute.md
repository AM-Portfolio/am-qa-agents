# Agent execute — AM Test Agent control plane

## REST

```http
POST /api/runs/execute
Content-Type: application/json
X-SPT-Api-Key: spt_sk_agent_localchange_me
Idempotency-Key: optional-unique-key

{
  "audience": "agent",
  "service": "am-analysis",
  "triggered_by": "agent",
  "wait": false
}
```

Or pass `config_id` for a specific profile. Non-developer audiences are forced to **1 VU × 1 iteration** with traces.

Poll: `GET /api/runs/{id}` or live fields on the run. Traces: `GET /api/runs/{id}/traces`.

### Playwright (UI via ui-test-agent)

Set `SPT_UI_TEST_AGENT_URL` (default `http://localhost:8130`). Portal: choose **playwright (UI)** then a UI profile/suite.

```http
POST /api/runs/execute
Content-Type: application/json

{
  "test_type": "playwright",
  "service": "am-modern-ui",
  "ui_profile": "PORTFOLIO_SMOKE_FLOW",
  "target_url": "http://localhost:9000",
  "triggered_by": "manual",
  "wait": false
}
```

Or suite: `"ui_suite": "smoke"` / `"release_gate"`.

UI steps land in the same Inspector as k6 (`kind: "ui_step"`). Artifacts:

- `GET /api/runs/{id}/traces` — step list
- `GET /api/runs/{id}/ui-report` — slim UI summary
- `GET /api/runs/{id}/playwright-trace` — Playwright `trace.zip` when available
- `GET /api/ui-test/profiles` — proxy to ui-test-agent profiles

Profiles alias: `/api/profiles` (same as `/api/configs`).

Compare: `GET /api/runs/compare?a={id}&b={id}`  
Baseline: `GET /api/runs/{id}/baseline`

## MCP (`/mcp`)

Mounts FastMCP streamable HTTP. Key tools:

- `spt_list_profiles`, `spt_get_profile`, `spt_ensure_default_profiles`
- `spt_execute_run`, `spt_get_run_live`, `spt_list_traces`, `spt_stop_run`
- `spt_compare_runs`, `spt_health`, `spt_list_apis`, `spt_resolve_target`

Prompts: `spt_agent_smoke`, `spt_dev_load`  
Resources: `spt://profiles/{id}`, `spt://runs/{id}`, `spt://runs/{id}/live`

## API keys (PoC ACL)

Bootstrap (hashed into DB on startup):

- `spt_sk_dev_localchange_me` → developer
- `spt_sk_agent_localchange_me` → agent

Override via `SPT_BOOTSTRAP_KEYS=role:name:secret,...`  
Set `SPT_ACL_REQUIRED=true` to require keys on mutating `/api/*` routes.

## Concurrent runs

`SPT_MAX_CONCURRENT_RUNS` (default 3) → HTTP 429 when exceeded.
