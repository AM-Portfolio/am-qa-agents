# SpecKit 10/10 — technical process & stack (how we build it)

This is **what we will do**, in order, with **which tech**. SpecKit (am-qa-agents) owns the product; am-specs owns contracts + generators.

## Big picture

```text
┌─────────────┐     harvest      ┌──────────────┐     generate      ┌─────────────────┐
│  Live APIs  │ ───────────────► │   am-specs   │ ─────────────────► │ Enterprise SDKs │
│ (services)  │                  │ OpenAPI SoT  │                    │ Java/Py/Dart    │
└─────────────┘                  │ tools.json   │                    │ MCP packs       │
                                 └──────┬───────┘                    └────────┬────────┘
                                        │                                     │
                                        │ snapshots + packs                   │
                                        ▼                                     ▼
                                 ┌──────────────────────────────────────────────────┐
                                 │              SpecKit (am-qa-agents)               │
                                 │  configure · orch generate · Try · E2E · publish │
                                 │  plugins: contract | java | python | dart | mcp  │
                                 └──────────────────────────────────────────────────┘
                                                        │
                        ┌───────────────────────────────┼───────────────────────────────┐
                        ▼                               ▼                               ▼
                 GitHub Actions                  Target env APIs                 Registries
                 (change-driven)                 (dev/preprod/prod)              (Maven/PyPI/pub)
```

---

## Tech stack by layer

| Layer | Tech | Repo / where |
|-------|------|----------------|
| Contract SoT | OpenAPI YAML/JSON, catalog YAML | **am-specs** `services/`, `catalog/` |
| Generators | Python 3.12, `openapi-generator-cli` (npx/jar) | **am-specs** `scripts/generate_*.py`, `packages/am_specs_lib/` |
| Enterprise SDKs | Java 17 (Maven), Python (pip/pyproject), Dart (pub) | **am-specs** `sdks/<id>/typed/{java,python,dart}/` + facade |
| MCP packs | JSON tools (`api_<service>_<opId>`) | **am-specs** `packages/mcp/` |
| SpecKit API | FastAPI (qa-agent `specs/`) | **am-qa-agents** |
| SpecKit UI | Flutter portal (qa-portal-ui) | **am-qa-agents** |
| SpecKit MCP control | FastMCP / SSE `spt_*` tools | **am-qa-agents** `/qa/mcp` |
| E2E runners | Python orchestration + Java/Maven, Python venv, Dart SDK subprocesses | **am-qa-agents** (new `e2e_sdk` plugins) |
| Domain enrich | am-mcp-server (SSE tools) | **am-core-services** (portfolio/symbol fill only) |
| CI/CD | GitHub Actions | am-specs workflows + SpecKit E2E job |
| Auth | Keycloak / identity JWT, Vault refs | existing Asrax |
| Verify | GitHub MCP / `gh` checks + artifacts | operator / agent |

---

## Process (phases → what we actually build)

### Phase 0 — Plan + **am-market pilot lock**
- Lock scorecard + pilot = `am-market-data`, `am-news`, `am-parser` only  
- **No code** · review `docs/speckit-10/`  

### Phase 1 — am-specs CI + change-driven skeleton
Same as before (generator pin, fail-hard, detect-changed).  

### Phase 2 — **am-market pilot only** (must finish first)
1. Generate typed SDK + MCP for market-data → news → parser  
2. E2E all three (contract + Java/Python/Dart + MCP)  
3. Pack includes sdks; CI green  
4. **Stop** — do not touch portfolio/trade/… yet  

### Phase 3 — Next wave (only after market Grown)
portfolio, oms, trade, analysis, docs, email, identity, …  

### Phase 4 — SpecKit hardening + remaining fleet  
### Phase 5 — Publish + 10/10 proof

---

## Runtime flow (one service change → production-ready)

```text
1. Engineer (or SpecKit) updates OpenAPI / harvest into am-specs
2. Push PR → detect-changed → only that service id
3. CI: generate typed SDK (3 langs) + MCP tools.json
4. CI: compile/import smoke (Java/Python/Dart)
5. SpecKit E2E job (same change set):
      auth → contract Try → Java SDK → Python SDK → Dart SDK → MCP tools
6. Report: GO / NO-GO
7. On GO + release: publish only that service’s packages
8. Consumers (apps/agents) pull new SDK / MCP — no manual per-lang project
```

---

## What *I* (implementation agent) will do when you approve execute

| Order | Work | Where |
|------:|------|--------|
| 1 | Phase 1: generator pin, fail-hard, detect-changed workflow | am-specs |
| 2 | Phase 2: backfill focus-11 SDKs+MCP, pack includes sdks, PR | am-specs |
| 3 | Prove change-driven with GitHub checks | am-specs CI |
| 4 | Phase 3: fleet backfill (or defer if you prioritize SpecKit E2E) | am-specs |
| 5 | Phase 4: SpecKit orch + E2E plugin runners + portal “Prove production” | am-qa-agents |
| 6 | Phase 5: publish-changed + gate on E2E + scorecard | am-specs + am-qa-agents |

I will **not** invent a second OpenAPI SoT inside QA, regenerate all SDKs on every PR, or use LLMs to generate SDKs/MCP (contract + openapi-generator only).

---

## Mental model (one sentence)

**am-specs builds the artifacts; SpecKit proves them in production-shaped E2E (HTTP + Java/Python/Dart SDKs + MCP) on change-driven CI; then publishes only what changed.**
