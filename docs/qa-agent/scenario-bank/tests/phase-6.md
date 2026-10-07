# Phase 6 tests — Warm + env policy

**Phase:** [../phase-6.md](../phase-6.md)

## Test

- [x] Two warm onboard → `llm_invoked=false` (`test_onboard_warm_second_pass`)
- [x] Unit: Contabo/prod select skips L5/security
- [x] Hash drift → needs_reinvent (unit)
- [ ] Live MCP `qa_bank_select` (restart Control MCP)

## Grown

- [x] Warm zero-LLM proven

## Evidence

- Contabo filter blocks `level5_abuse` + `security`
- Hash mismatch → `needs_reinvent=true`, `invent_complete=false`
- Date: 2026-10-06
