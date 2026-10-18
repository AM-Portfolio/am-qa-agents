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
- [x] SpecKit CI **live E2E** gate for each pilot id — `scripts/e2e_pilot.py` (contract + Python/Java SDK + MCP) wired in `sdk-changed.yml` after smoke ([E2E_PROD.md](E2E_PROD.md)); Dart runtime deferred (analyze in smoke)
- [x] Prove change-driven: `test_detect_changed_services.py` — news-only OpenAPI path → `["am-news"]` (without `--union-pilots`)
- [x] am-specs generators + CI on `master` (GitHub Actions green for generate/smoke/artifact; E2E GO when DEV tunnel up)
- [x] Update [INVENTORY.md](INVENTORY.md) pilot rows

## Test

Use [tests/phase-2.md](tests/phase-2.md) + [VERIFY.md](VERIFY.md).

- [x] 3/3 pilot services enterprise SDK + MCP local verify (`verify_local.py`)
- [ ] Live E2E **GO** on DEV (blocked while Cloudflare tunnel 1033/530 on `am-dev.asrax.in` — job exits `skipped: infra_unreachable`, not false green)
- [x] No portfolio/trade/… SDK work in this phase’s PRs
- [x] Pack artifact contains market sdks (`sdk-publish-am-*` on Actions)

## Grown

- [ ] **am-market pilot complete** — generate/smoke/E2E gate landed; mark Grown after 3/3 E2E GO run URL when DEV tunnel is healthy — then start [phase-3.md](phase-3.md)

## Stop if fail

Any of market-data / news / parser fails typed or E2E → fix before Phase 3.

## Refuse

- No generating portfolio, trade, oms, identity, docs, etc. in this phase
- No “commit FAILED TYPED.md and move on”
