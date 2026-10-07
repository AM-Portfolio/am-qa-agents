# Phase 4 tests — Bank store

**Phase:** [../phase-4.md](../phase-4.md)

## Test

- [x] Unit: upsert seed rows (`test_scenario_bank_store.py`)
- [x] Unit: 200 cap eviction (non-seed first; fixture uses cap=3)
- [x] Unit: invent lock single winner
- [x] Unit: dedupe_key collapses duplicates
- [x] Onboard seeds bank (`bank.count` after `onboard_plugin`)
- [ ] Live catalog/bank MCP list after restart (`qa_bank_list`)

## Grown

- [x] Seed bank without LLM

## Evidence

- Cap / lock / dedupe unit green
- Onboard writes seed rows under `QA_SCENARIO_BANK_DIR`
- Date: 2026-10-06
