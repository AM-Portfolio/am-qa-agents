# Tests — Phase 2 (am-market pilot only)

**Verify:** GitHub MCP + [E2E_PROD.md](../E2E_PROD.md) + [VERIFY.md](../VERIFY.md).

## Scope gate

- [ ] PRs in this phase touch **only** `am-market-data` / `am-news` / `am-parser` (plus shared CI/docs)
- [ ] No portfolio/trade/oms/identity SDK commits

## Per pilot service (all 3)

- [ ] typed java/python/dart + TYPED OK + enterprise coords
- [ ] MCP pack entry
- [ ] E2E GO: contract + Java + Python + Dart + MCP

## Pipelines

- [ ] validate + build green (GitHub MCP)
- [ ] Change-driven: news-only OpenAPI PR regenerates news only
- [ ] Pack includes market `sdks/`

## Grown

3/3 pilot E2E GO → unlock Phase 3.
