# Platform SPT catalog (local)

`spt.yaml` registrations for AM platform services so SPT can fetch **prod Swagger**
(`/openapi.json` / `/v3/api-docs`) and generate MCP tools.

Point `SPT_CATALOG_EXTERNAL` at this folder (or append with `;` after core-services):

```
SPT_CATALOG_EXTERNAL=F:/am-repos/am-repos/am-core-services/services;F:/am-repos/am-repos/am-qa-agents/qa-agent/catalog-external
```

Refresh tools: MCP `spt_refresh_openapi_tools` or

```bash
python -c "from specs.openapi_tools.registry import refresh_tools_from_prod; print(refresh_tools_from_prod(environment='prod'))"
```
