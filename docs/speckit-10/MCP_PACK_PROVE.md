# SpecKit / QA — prove MCP pack tools (product fleet)

**Agent runtime** stays [`am-mcp-server`](../../../am-core-services/services/am-mcp-server/docs/OWNERS_MCP.md).  
This page is **prove-only**: call pack `tools.json` against live **DEV** and write a report.

- **MCP:** all ~25 am-specs packs (~853 `api_*` tools) stay registered on DEV.
- **QA catalog + prove:** **product HTTP services only** (~16), same SKIP as `sync_catalog_from_am_specs.py` (agents/meta excluded).

For SSE detail see [MCP_SSE_PILOT_PROVE.md](MCP_SSE_PILOT_PROVE.md).

## Operator one-liner (fleet)

From the `am-specs` checkout:

```bash
python scripts/speckit_pilot_workflow_prove.py --env dev --services product --qa-url https://am-dev.asrax.in/qa
```

Outputs:

- `dist/speckit-fleet-workflow-report.json` / `.html` — overall verdict
- `dist/mcp-pack-report-<service>.json` / `.html` — pack HTTP per product service
- `dist/mcp-sse-fleet-report.json` / `.html` — SSE `tools/call` for fillable `api_*`

Pilots-only: `--services pilots` (writes `speckit-pilot-workflow-report.*`).

## Pack HTTP only

```bash
python scripts/mcp_pack_runner.py --service am-portfolio --env dev --caller am-qa-agents --group all
```

## Datasets → QA

```bash
python scripts/render_dataset_pack.py --service am-subscription --tier working --env dev
python scripts/sync_datasets_to_qa.py --service am-subscription --qa-url https://am-dev.asrax.in/qa
```

Catalog:

```bash
# am-qa-agents
python qa-agent/scripts/sync_catalog_from_am_specs.py --apply-dev
```

## Verdict

Per service `go` when: health/probe OK, `passed >= min(5, invoked)`, `fail_ratio <= 0.50`.  
Overall fleet `go` only if **all** product services `go` on both pack HTTP and SSE.

Do **not** stand up a second MCP server in SpecKit for this.
