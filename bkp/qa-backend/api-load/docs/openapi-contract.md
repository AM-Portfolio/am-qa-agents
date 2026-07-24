# SPT ↔ service OpenAPI contract

SPT builds Try-it / load payloads from the **live OpenAPI document** only.
There is **zero coupling** to service source code (no Java imports, no hard-coded analysis enums).

## Allowed

| SPT may | How |
|---------|-----|
| Fetch `{target}{openapi.path}` | Via `spt.yaml` registration |
| Read `enum`, `example`, `default`, `format` | Generic builder |
| Store overlays + payload sets | `{data_dir}/openapi_overlays`, `{data_dir}/payloads` |
| Call Try proxy | `/api/catalog/{service}/try/...` |
| Optional MCP enrich | `SPT_PAYLOAD_MCP_ENRICH` → am-mcp-server SSE (`get_portfolio_overviews`, `get_holdings`, …) fills **placeholder** params only during ensure-working |
| Optional LLM HTTP | `SPT_PAYLOAD_LLM_FALLBACK` + `SPT_FIN_API_TESTING_URL` (off by default; **after** failed Try) |

## Forbidden

- Importing `am-core-services` / service SDKs into SPT
- `if service == "am-analysis"` schema special cases in the builder
- Hard-coded timeframe / entity-type lists in JS or Python
- Overwriting non-placeholder overlay/set values with MCP facts

## Ensure-working order

1. Build (overlay → example → schema)
2. MCP enrich placeholders only (`source=mcp` when fields change)
3. Try once
4. On non-2xx: optional LLM → re-Try (`source=llm-fallback`)
5. On 2xx: write overlay + payload set

**Identity caveat:** MCP session uses SPT identity JWT; tool data may still be scoped to the mcp-server service account. Mismatched IDs can make Try fail — that is expected; LLM is last resort.

Do not confuse endpoints:

| URL | Role |
|-----|------|
| SPT `/mcp` | SPT control tools (`spt_*`) |
| `am-mcp-gateway` | LLM / agent gateway |
| `am-mcp-server` `/sse` | Finance tools for enrich |

## Service obligations

Publish complete springdoc OpenAPI. See:

- [am-core-services openapi-spec-guidelines.md](../../../../am-core-services/docs/openapi-spec-guidelines.md)
- [spt-onboarding.md](../../../../am-core-services/docs/spt-onboarding.md)

When a service adds an enum constant, SPT picks it up on the next OpenAPI fetch — no SPT change.

## APIs

| Endpoint | Purpose |
|----------|---------|
| `POST /api/payloads/build` | Schema-first build (overlay → example → schema); **no** MCP/LLM |
| `POST /api/payloads/ensure-working` | Build → MCP enrich → Try → optional LLM → write set+overlay on 2xx |
| `POST /api/payloads/prepare-mcp` | Scan service (or all catalog) OpenAPI ops; MCP-fill `portfolioId` / `PORTFOLIO` `{id}`; write overlays |
| `GET /api/catalog/{service}/openapi/effective` | Live doc + SPT overlay |
| MCP `spt_build_payload` / `spt_ensure_working_payload` / `spt_prepare_mcp_payloads` | Same for agents |

`source` values: `set` | `example` | `schema` | `mcp` | `llm-fallback`.
