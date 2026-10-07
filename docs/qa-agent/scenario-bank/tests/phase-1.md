# Phase 1 tests — Plugins

**Phase:** [../phase-1.md](../phase-1.md)

## Test

- [x] `pytest qa-agent/ui_evidence/tests/test_plugin_loader.py -q` green
- [x] Local `list_plugins` → am-subscription + am-identity enabled
- [x] `resolve_api_pack_default(subscription_module)` → subscription
- [x] `set_plugin_enabled` false → absent; true → present
- [x] `catalog_bundle` returns API flow ids
- [ ] MCP `qa_plugin_*` against running Control MCP (after restart + `am ai mcp-sync`)

## Grown

- [x] Detach/reattach proven locally without core edit for new folder pattern

## Evidence

**2026-10-06:** pytest plugin_loader — green; plugins `am-subscription`, `am-identity` under `qa-agent/plugins/`; gateway/ops use `resolve_api_pack_default`.
