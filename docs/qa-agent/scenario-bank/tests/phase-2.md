# Phase 2 tests — Contract smoke

**Phase:** [../phase-2.md](../phase-2.md)

## Test

- [x] Unit: empty tools → `onboard_blocked`
- [x] Unit: empty tools → no invent (`llm_invoked=false`)
- [x] Unit: smoke OK → knowledge file written
- [x] `skills.yaml` present with L1–L5 ids
- [ ] MCP `qa_plugin_onboard` env=dev against live SPT

## Grown

- [x] Smoke fail never invents (unit)

## Evidence

**2026-10-06:** `test_scenario_bank_onboard.py` — 5 passed; knowledge under tmp + `ui_evidence/data/scenario_bank/knowledge/` on live onboard.
