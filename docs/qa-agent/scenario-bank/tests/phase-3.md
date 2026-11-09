# Phase 3 tests — Data prep

**Phase:** [../phase-3.md](../phase-3.md)

## Test

- [x] Unit: login fail → fail-closed on **dev** (`test_scenario_bank_data_prep.py`)
- [x] Unit: Contabo/prod path never calls grant
- [ ] MCP `qa_plugin_prep` env=dev → structured ok/error (restart Control MCP)
- [ ] Optional live **dev** prep once (soft)

## Grown

- [x] Fail-closed unit green

## Evidence

- Unit: `prepare_subscription(env=dev)` without `SPT_AUTH_*` → `ok=false`, `fail_closed=true`, no `call_tool`
- Unit: `assert_only=True` → `ensure_grant` SKIPPED with assert_only reason; grant tool never invoked
- `dig` normalized to `dev`
- Date: 2026-10-06
