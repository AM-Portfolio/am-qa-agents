# Phase 7 tests — Pack run

**Phase:** [../phase-7.md](../phase-7.md)

## Test

- [x] Unit: prep fail-closed stops execute (`test_scenario_bank_pack_runner.py`)
- [x] Unit: silent SKIPPED → NO_GO
- [ ] Local live: `python -u ui_evidence/scripts/run_subscription_module_complete.py --skip-ui` (SPT)
- [ ] MCP `qa_plugin_run_pack` / ops start (restart Control MCP)

## Grown

- [x] Unit pack path exercised; live soft

## Evidence

- prep_fail_closed → `executed=false`, decision NO_GO
- refused_silent_skip when execute returns SKIPPED
- Date: 2026-10-06
