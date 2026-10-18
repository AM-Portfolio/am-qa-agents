# SpecKit / QA — prove MCP pack tools (market-data)

**Agent runtime** stays [`am-mcp-server`](../../../am-core-services/services/am-mcp-server/docs/OWNERS_MCP.md).  
This page is **prove-only**: call pack `tools.json` against live DEV and write a report.

## Command (am-specs owns the runner)

From the `am-specs` checkout:

```bash
# Optional: ASRAX_API_KEY / ASRAX_API_SECRET (or Vault via resolve_key_secret)
python scripts/mcp_pack_runner.py --service am-market-data --env dev --caller am-qa-agents
```

Outputs:

- `dist/mcp-pack-report-am-market-data.json`
- `dist/mcp-pack-report-am-market-data.html`

Scope: **GET** tools in group **`core`** (plus `/health/status`). No POST/PUT/DELETE.

## QA portal operators

1. Ensure am-specs is current and `services/am-market-data/tools.json` exists.
2. Run the command above (local or CI job).
3. Open the HTML report; verdict `go` / `no_go` is in JSON `verdict`.

Do **not** stand up a second MCP server in SpecKit for this.
