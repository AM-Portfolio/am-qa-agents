# Phase 4 — Bank store + invent lock

**Goal:** ~200-cap bank with dedupe, `invent_complete` / `needs_reinvent`, invent lock TTL. No LLM required.

**Prereq:** [phase-3.md](phase-3.md) Grown.

## Implement

- [x] Bank store JSON under `ui_evidence/data/scenario_bank/` (`QA_SCENARIO_BANK_DIR` override)
- [x] Cap 200 / `(service, env)`; `dedupe_key`
- [x] Invent lock per `(service, env)` with TTL
- [x] Seed rows from hand-seeded skills after onboard
- [x] Unit: cap, lock, dedupe
- [x] MCP `qa_bank_list`

## Test

Use [tests/phase-4.md](tests/phase-4.md).

- [x] Seed rows listed via bank unit / onboard `bank` field
- [x] Concurrent lock unit: one winner
- [ ] Live MCP `qa_bank_list` after Control MCP restart

## Grown

- [x] Bank holds seed without invent
- [x] Unlocks Phase 5 invent into same store

## Stop if fail

No persistence → do not invent (would lose rows).

## Refuse

- Auto-promote bank rows into `SUITE_PROFILES`
- Cap >200 without explicit plan change
