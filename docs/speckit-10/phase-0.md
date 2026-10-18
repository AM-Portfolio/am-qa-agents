# Phase 0 — Inventory + **am-market pilot lock**

**Goal:** Lock baseline scorecard **and** lock **am-market** as the only pilot domain. No other services enter generate/E2E until market pilot is Grown. **No** SDK generate in this phase. **No** CI mutation.

**Prereq:** Read [README.md](README.md) locked decisions.

## Pilot set (locked) — am-market monorepo

| Service id | Repo path |
|------------|-----------|
| `am-market-data` | am-market / am-market-data |
| `am-news` | am-market / am-news |
| `am-parser` | am-market / am-parser |

**Rule:** Phases 1–2 (+ market E2E) must finish and pass tests for **these three only**. Portfolio, trade, oms, identity, docs, … wait until Phase 3+.

## Implement

- [x] Audit full focus-11 for awareness (see [INVENTORY.md](INVENTORY.md))
- [x] Score dimensions 0–10 (README scorecard “Now” column)
- [x] List blockers B1–B8, S1–S7, D1–E1
- [x] Lock product name SpecKit + am-specs SoT
- [x] Lock **am-market pilot** (market-data, news, parser) — first slice
- [x] Operator review / accept this doc pack **including pilot-first rule**

## Test

Use [tests/phase-0.md](tests/phase-0.md).

- [x] INVENTORY marks pilot vs later waves
- [x] README phase map says market-first
- [x] No generate_sdk / deploy during this phase

## Grown

- [x] Phase 0 accepted; ready for Phase 1 CI gates (**scoped to support market pilot**)

## Stop if fail

Inventory disputed, naming rejected, or pilot set disputed → do not start Phase 1.

## Refuse

- No `generate_sdk.py` for non-market services
- No CI workflow edits yet
- No expanding pilot to portfolio/trade in Phase 0–2
