# SpecKit 10/10 — Inventory (baseline)

**Date:** 2026-10-18 · **Source:** am-specs catalog + `sdks/` + `TYPED.md` audit. No secrets.

## Pilot-first (locked)

**Phase 2 only:** am-market — `am-market-data`, `am-news`, `am-parser`.  
**Phase 3+:** all other rows. Do not generate/E2E non-pilot until pilot Grown.

## Focus service matrix

| Service | openapi + tools.json / MCP | Thin SDK | Typed non-empty | TYPED.md | Enterprise score (0–10) |
|---------|----------------------------|----------|-----------------|----------|------------------------:|
| am-market-data **(PILOT)** | Y + MCP routes/models | Y + Service | **Y** (53 schemas) | OK | 9 |
| am-news **(PILOT)** | Y + MCP routes | Y + Service | **Y** | OK | 9 |
| am-parser **(PILOT)** | Y + MCP routes | Y + Service | **Y** | OK | 9 |
| am-portfolio (wave 2) | Y | Y | empty | FAILED | 2 |
| am-oms | Y | Y | **Y** | OK | 8 |
| am-trade-management-service | Y | Y | empty | FAILED | 2 |
| am-analysis | Y | Y | empty | FAILED | 2 |
| am-document-processor | Y | Y | empty | FAILED | 2 |
| am-cloudinary-manager | Y | Y | empty | FAILED | 2 |
| am-email-extractor | Y | Y | **Y** | OK | 8 |
| am-identity | Y | Y | empty | FAILED | 2 |

**Focus typed readiness:** 2/11 · **Focus average score:** ~2.7/10 · **Publishable enterprise artifacts:** 0/11

## Cross-cutting findings

| ID | Finding |
|----|---------|
| B1 | ~~am-specs CI does not install openapi-generator~~ → pinned in validate + sdk-changed |
| B2 | ~~soft-ok~~ → `--require-typed` + pilot auto-require |
| B3 | ~~thin-only~~ → typed required for SpecKit pilot allowlist |
| B4 | ~~am-market-data no sdks/~~ → generated |
| B5 | ~~`publish_pack.py` omits `sdks/`~~ → pilot + complete typed included |
| B6 | ~~ENABLEMENT never --sdk~~ → SpecKit enterprise track documented |
| B7 | Package coords: thin `asrax-*` vs typed `org.openapitools:openapi-java-client`; versions 0.1.0 vs 1.0.0 |
| S1–S3 | SpecKit/QA: no am-specs orch; live OpenAPI only; packs not loaded |
| S4 | Prepare MCP → am-mcp-server (domain); separate from contract packs |
| S5–S7 | QA Portal branding; no multi-tenant; docs QA-only |
| E2E | am-specs `scripts/e2e_pilot.py` + `sdk-changed` job: contract + Python/Java SDK + MCP on DEV for pilots; Dart analyze via smoke; GO pending healthy `am-dev.asrax.in` tunnel ([E2E_PROD.md](E2E_PROD.md)) |

## Repos

| Repo | Role |
|------|------|
| am-specs | Contract SoT + generators |
| am-qa-agents | SpecKit runtime (rename product face) |
| am-core-services / am-mcp-server | Domain MCP enrich + future Java SDK consumer |

## Re-measure

After Phase 2 / 3: update this table and scores in [README.md](README.md).
