# Phase 3 — Hand-seeded data_prep (**dev**)

**Goal:** Plugin `data_prep.entry` / `seed.py`: SPT login → plans/me; **dev** optional ensure; Contabo assert-only; fail-closed on **dev**.

**Prereq:** [phase-2.md](phase-2.md) Grown.

## Implement

- [x] `seed.py` on am-subscription + am-identity (`prepare` → `data_prep.prepare_*`)
- [x] Fail-closed envs: `[dev]`
- [x] Assert-only envs: Contabo prod (`assert_only_envs`)
- [x] MCP `qa_plugin_prep`
- [x] Unit tests for fail-closed + assert-only

## Test

Use [tests/phase-3.md](tests/phase-3.md).

- [x] Local unit fail-closed green
- [ ] MCP prep env=dev returns structured ok/error (no secrets) — needs restarted Control MCP

## Grown

- [x] Prep path reusable by Phase 7 pack
- [x] Unlocks Phase 4 bank seed rows

## Stop if fail

Login/me cannot be asserted in unit → do not claim prep ready.

## Refuse

- LLM-only data_generator (hand seed required)
- Contabo prod grant/ensure calls
