# SpecKit — production E2E gate (contract + SDK + MCP)

**Locked product promise:** SpecKit is not only “Try API with test data.” Before a service (or change) is production-ready, SpecKit proves **end-to-end**:

1. **Contract** — OpenAPI + working payloads / SPT cases against the target env  
2. **SDKs (all plugins)** — generated enterprise clients actually call the service  
3. **MCP tools** — pack tools invoke the same operations successfully  

No extra manual project per language. One SpecKit run (or CI job for the **changed** service set) is enough to ship.

## Surfaces under test

| Surface | What SpecKit runs | Pass |
|---------|-------------------|------|
| HTTP / contract | Snapshot OpenAPI + payload sets / ensure-working / Try | 2xx (or documented expected) on critical ops |
| **Java SDK** | Resolve published or workspace `typed/java` (+ facade); call N critical ops | Compile + runtime success |
| **Python SDK** | Same for `typed/python` | Import + runtime success |
| **Dart SDK** | Same for `typed/dart` | Analyze + runtime success (or integration harness) |
| **MCP pack tools** | Load `packages/mcp/services/<id>/tools.json`; call tools with same fixtures | Tool result OK / HTTP success |
| Auth | Identity / tenant credentials from Vault refs | All surfaces share same caller identity |

Critical ops list: from `OPERATIONS.md` / data-gen “working” set (happy path + one auth failure negative).

## When it runs

| Trigger | Scope |
|---------|--------|
| SpecKit “Prove production” / release gate | Selected service(s) or change set |
| am-specs CI after `generate-changed` | **Only** services in detect-changed set ([PIPELINE.md](PIPELINE.md)) |
| Explicit backfill | Focus/fleet once |

## Flow

```text
am-specs snapshot + generated SDK/MCP
        ↓
SpecKit E2E job (per changed service)
  ├─ contract Try (payloads)
  ├─ Java SDK plugin runner
  ├─ Python SDK plugin runner
  ├─ Dart SDK plugin runner
  └─ MCP pack tool runner
        ↓
single report: go / no-go for production
```

## Plugin runners (implement in SpecKit / qa-agent)

- Shared fixture: base URL, bearer/API key, portfolio/symbol from Prepare MCP when needed  
- Language plugins call **`*Service.from_env(env)`** (enterprise SDK), not raw thin stubs  
- MCP runner: load `packages/mcp/services/<id>/pack.json` → set env once → invoke tools by `routes.json` tag (same as Service routes)  
- **Market-data pack prove (GET/core):** am-specs `python scripts/mcp_pack_runner.py --service am-market-data --env dev` → `dist/mcp-pack-report-am-market-data.{json,html}` — see [MCP_PACK_PROVE.md](MCP_PACK_PROVE.md)  
- Report artifact: JSON + HTML (pass/fail per tool); portal UI optional later

## Production go criteria (service change)

- [ ] Contract E2E green on target env (dev → preprod → prod as policy)  
- [ ] Java + Python + Dart SDK E2E green (or explicit waive with SCORECARD exception)  
- [ ] MCP pack tools E2E green  
- [ ] GitHub CI for that change set green ([VERIFY.md](VERIFY.md))  
- [ ] Publish (if releasing) only after go  

**Refuse:** “SDK generated” without SpecKit E2E · “MCP tools listed” without invoke · contract-only green as production sign-off.
