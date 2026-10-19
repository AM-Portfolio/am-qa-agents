# SpecKit — prove product tools via am-mcp-server SSE (DEV only)

**Runtime:** `am-mcp-server` (not SpecKit as host).  
**MCP packs:** all ~25 services (~853 tools) stay live.  
**Prove / QA feed:** product HTTP set (~16), not agent/meta packs.  
**Env:** **DEV only** (`https://am-dev.asrax.in/mcp`).

## Preferred: fleet workflow report

From `am-specs`:

```bash
python scripts/speckit_pilot_workflow_prove.py --env dev --services product --qa-url https://am-dev.asrax.in/qa
```

Bar: overall `go` in `dist/speckit-fleet-workflow-report.json` (pack HTTP + SSE; each product service `passed >= min(5, invoked)` and `fail_ratio <= 0.50`).

## Deploy (after MCP server changes)

From `am-core-services/services/am-mcp-server`:

```bash
python scripts/sync_contract_packs.py
am deploy doctor --env dev
am deploy --env dev --via gitops --rebuild
```

## SSE-only prove

```bash
cd am-specs
python scripts/mcp_sse_pilot_prove.py --base https://am-dev.asrax.in/mcp --services product --out-dir dist
# pilots only:
python scripts/mcp_sse_pilot_prove.py --services pilots --out-dir dist
```

Outputs:

- Fleet: `dist/mcp-sse-fleet-report.json` / `.html`
- Pilots: `dist/mcp-sse-pilot-report.json` / `.html`

## Verdict

`go` when **each** product service in the prove set meets the pack/SSE threshold above.  
A single smoke pass per service is **not** enough for fleet `go`.
