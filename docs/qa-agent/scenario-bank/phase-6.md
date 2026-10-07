# Phase 6 — Warm path + env policy

**Goal:** Warm + invent_complete + no hash drift → zero LLM. Contabo prod blocks L5/security/mutate before select.

**Prereq:** [phase-5.md](phase-5.md) Grown or N/A (seed-only warm still required).

## Implement

- [x] Warm skip invent when invent_complete and hash match
- [x] Env filter on select-few (`env_policy.py` + MCP `qa_bank_select`)
- [x] Hash drift → `needs_reinvent` (`hash_drift.py` in onboard)
- [x] Unit: Contabo L5 never selected

## Test

Use [tests/phase-6.md](tests/phase-6.md).

- [x] Two warm local onboards: `llm_invoked=false` (Phase 5 invent tests)
- [x] Prod/contabo select shows L5 skipped
- [ ] Live MCP `qa_bank_select` after Control MCP restart

## Grown

- [x] Warm zero-LLM proven (unit)
- [x] Unlocks Phase 7 full pack

## Stop if fail

Warm still calls LLM without force_llm → fix before pack CI.

## Refuse

- Running L5 on Contabo prod "just to see"
