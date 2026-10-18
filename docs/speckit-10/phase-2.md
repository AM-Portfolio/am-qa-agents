# Phase 2 — **am-market pilot** (SDK + MCP + E2E)

**Goal:** Finish and test **only** am-market services end-to-end. Score: typed + pack + prod E2E green for the pilot set. **No** other domains until Grown.

**Prereq:** [phase-1.md](phase-1.md) Grown.

**Owner:** SpecKit triggers / reviews; generators + CI in **am-specs**.

## Pilot set (only)

| id | Notes (baseline) |
|----|------------------|
| `am-market-data` | Enterprise Service + 53 schemas + MCP routes (local verify OK) |
| `am-news` | Enterprise Service + MCP routes (local verify OK) |
| `am-parser` | Enterprise Service + MCP routes (local verify OK) |

## Implement

- [x] Backfill typed Java/Python/Dart + MCP for **market-data → news → parser** only (**local / CI artifacts — never git-commit `sdks/`**)
- [x] Enterprise assemble: `*Service.from_env` + primary `api/`/`models/` (not hollow stubs)
- [x] OpenAPI DTO harvest for market-data (schemas ≫ 5)
- [x] Enterprise MCP: `pack.json` / `routes.json` / `models/` + tool `_meta.route`
- [x] Smoke: mvn / python Service import / dart analyze (`scripts/smoke_typed_sdk.py`)
- [x] `publish_pack` includes `sdks/` in **publish artifacts** (gitignored locally)
- [x] Policy: `sdks/` in `.gitignore`; validate forbids tracked `sdks/`; local gate = `scripts/verify_local.py`
- [ ] SpecKit (or CI) **live E2E** for each pilot id ([E2E_PROD.md](E2E_PROD.md))
- [ ] Prove change-driven: OpenAPI change on `am-news` only regenerates news
- [ ] PR(s) am-specs generators/docs only; GitHub MCP green
- [x] Update [INVENTORY.md](INVENTORY.md) pilot rows

## Test

Use [tests/phase-2.md](tests/phase-2.md) + [VERIFY.md](VERIFY.md).

- [x] 3/3 pilot services enterprise SDK + MCP local verify (`verify_local.py`)
- [ ] Live E2E GO on target env
- [ ] No portfolio/trade/… SDK work in this phase’s PRs
- [x] Pack artifact contains market sdks

## Grown

- [ ] **am-market pilot complete** — only then start [phase-3.md](phase-3.md)

## Stop if fail

Any of market-data / news / parser fails typed or E2E → fix before Phase 3.

## Refuse

- No generating portfolio, trade, oms, identity, docs, etc. in this phase
- No “commit FAILED TYPED.md and move on”
