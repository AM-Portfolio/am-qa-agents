# Tests — Phase 2 (am-market pilot only)

**Verify:** GitHub MCP + [E2E_PROD.md](../E2E_PROD.md) + [VERIFY.md](../VERIFY.md).

## Scope gate

- [x] Phase work touches **only** `am-market-data` / `am-news` / `am-parser` (plus shared CI/docs/generators)
- [x] No portfolio/trade/oms/identity SDK commits

## Per pilot service (all 3)

- [x] typed java/python/dart + TYPED OK + enterprise coords (CI `sdk-publish-am-*` artifacts)
- [x] MCP pack entry (`services/<id>/mcp/` + `packages/mcp/services/<id>/`)
- [ ] E2E GO: contract + Java + Python + MCP (Dart analyze via smoke) — gate landed (`scripts/e2e_pilot.py`); **GO** when `am-dev.asrax.in` tunnel healthy
- [x] Market-data MCP pack prove (GET/core): `python scripts/mcp_pack_runner.py --service am-market-data --env dev` → `dist/mcp-pack-report-am-market-data.{json,html}` — verdict **go** (13/24 passed, health_ok; see [MCP_PACK_PROVE.md](../MCP_PACK_PROVE.md))

## Pipelines

- [x] validate + sdk-changed generate/smoke green (GitHub Actions)
- [x] Change-driven proof: `packages/am_specs_lib/tests/test_detect_changed_services.py` — news-only OpenAPI → `["am-news"]`
- [x] Pack includes market `sdks/` (Actions artifacts, not GitHub Packages)

## Grown

3/3 pilot E2E **GO** (not infra skip) → unlock Phase 3.
