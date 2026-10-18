# SpecKit 10/10 — enterprise SDK + MCP + orchestrator

**Home:** [am-qa-agents](../../) — SpecKit (product face of today’s QA Agent / SPT) owns this track.

Contract generators stay in **am-specs**; SpecKit **orchestrates** configure → generate → **production E2E** (contract + SDK plugins + MCP tools) → publish. Goal: **3.0/10 → 10/10** — ship without extra per-language effort.

Related: [TECH_FLOW.md](TECH_FLOW.md) (process + stacks) · [qa-agent design](../qa-agent/README.md) · [E2E_PROD.md](E2E_PROD.md) · [PIPELINE.md](PIPELINE.md) · [VERIFY.md](VERIFY.md) · [am-specs ARCHITECTURE](../../../am-specs/docs/ARCHITECTURE.md) · [ENABLEMENT](../../../am-specs/docs/ENABLEMENT.md) · [CONSUMING_ASRAX](../../../am-specs/docs/CONSUMING_ASRAX.md) · [INVENTORY.md](INVENTORY.md)

## Recommendation (locked)

| Item | Value |
|------|--------|
| Product name | **SpecKit Agent** (short: **SpecKit**) |
| Asrax tenant | **Asrax SpecKit** |
| Contract SoT | **am-specs** (OpenAPI, tools.json, enterprise SDKs, Postman) |
| Generators | Stay in am-specs (`generate_sdk.py`, `generate_mcp_tools.py`, `enable_service.py`, `publish_pack.py`) |
| **LLM for SDK/MCP generate** | **No** — OpenAPI contract + openapi-generator only (deterministic, contract-faithful). Optional LLM stays only on legacy ensure-working payload fallback (off by default), never in generate/publish/E2E gate |
| SpecKit role | Orchestrate configure → generate → **E2E prove** (contract + Java/Python/Dart SDKs + MCP packs) → publish; does **not** reimplement generators |
| SpecKit testing | Not contract/payload-only — must E2E-test **SDK plugins** (Java and others) **and MCP tools** so production needs no extra effort ([E2E_PROD.md](E2E_PROD.md)) |
| SDK bar | **Enterprise typed** (models + API clients) for **Java, Python, Dart** — not thin stubs |
| Thin templates | Auth/config **facade** over typed only |
| **Pipeline regen** | **Change-driven only** — regenerate SDK/MCP **only** for services whose OpenAPI/meta changed (see [PIPELINE.md](PIPELINE.md)). Full fleet = explicit backfill / `workflow_dispatch` |
| Overall target | **10/10** on every scorecard dimension (see below) |
| Wave Asrax publish | Git commit/PR first; then GH Packages / PyPI / pub (**publish only changed** packages) |
| External companies | Tenant profile: Maven / PyPI / pub credential refs (Vault) |
| Domain MCP | **Runtime SoT:** `am-core-services/services/am-mcp-server` only (domain + contract packs). **am-specs** = pack generation only. SpecKit does not host an MCP server. |
| Verification | GitHub MCP / CI green per [VERIFY.md](VERIFY.md) — local-only does not count |
| Internal repo (near term) | Keep `am-qa-agents` / `qa-agent` / `spt_*`; SpecKit is product face |

```text
Phase 0: inventory + lock am-market pilot (market-data, news, parser)
  → Phase 1: CI gates + change-driven pipeline (A0–A1)
  → Phase 2: MARKET PILOT only — generate SDK/MCP + E2E + prove (must Grown first)
  → Phase 3: next services (portfolio, trade, oms, …) only after market Grown
  → Phase 4: remaining fleet + SpecKit product hardening
  → Phase 5: publish + 10/10 proof
```

**Pilot-first (locked):** Do not start portfolio/trade/identity/… generate or E2E until **am-market** (`am-market-data`, `am-news`, `am-parser`) is fully done and tested.

## Scorecard (now → 10)

| Dimension | Now | After Ph 1–3 | After Ph 4 | After Ph 5 | **10 means** |
|-----------|----:|-------------:|-----------:|-----------:|--------------|
| Contract OpenAPI (all enabled) | 9 | 10 | 10 | 10 | Every `enabled:true` has OpenAPI + meta |
| MCP tools.json / assemble | 8 | 9 | **10** | 10 | Packs complete; SpecKit serves packs |
| Thin/facade layout | 6 | **10** | 10 | 10 | All enabled have facade/wrap; market-data included |
| Enterprise typed SDK | 2 | **10** | 10 | 10 | All enabled: typed java+python+dart OK + smoke |
| Buildable / publishable pkgs | 1 | 8 | 8 | **10** | `com.asrax` coords; pack+registry publish |
| CI gate enterprise SDK | 1 | **10** | 10 | 10 | Generator pinned; `--require-typed`; validate fails empty typed |
| Docs / policy alignment | 3 | 9 | **10** | 10 | One story; no “never --sdk” contradiction |
| SpecKit orchestrator | 2 | 2 | **10** | 10 | Branding + snapshots + generate/PR + pack MCP |
| **Prod E2E (contract+SDK+MCP)** | **1** | 2 | **8** | **10** | SpecKit runs contract Try + Java/Python/Dart SDK + pack MCP; single go/no-go |
| Multi-tenant registry | 0 | 0 | 0 | **10** | Asrax registries + tenant YAML dry-run |
| Core MCP ↔ generated SDK | 3 | 3 | 4 | **10** | Focus callees via generated Java SDK; agents on packs |
| **Overall** | **3.0** | **~6.5** | **~8.0** | **10.0** | Phase 5 proof |

## Phase map

| Order | Phase | File | Status |
|------:|-------|------|--------|
| 0 | Inventory + **am-market pilot lock** | [phase-0.md](phase-0.md) | **Docs ready — review** |
| 1 | CI gates + change-driven pipeline | [phase-1.md](phase-1.md) | Docs ready — implement when started |
| 2 | **am-market pilot** SDK + MCP + E2E | [phase-2.md](phase-2.md) | Blocked until Phase 1 Grown |
| 3 | Next wave (portfolio, trade, oms, …) | [phase-3.md](phase-3.md) | **Blocked until Phase 2 market Grown** |
| 4 | SpecKit orch hardening + remaining fleet | [phase-4.md](phase-4.md) | Blocked until Phase 3 Grown |
| 5 | Publish + 10/10 proof | [phase-5.md](phase-5.md) | Blocked until Phase 4 Grown |

Tests: [`tests/`](tests/).

## Pilot services (Phase 2 only) — am-market

`am-market-data`, `am-news`, `am-parser`

## Later waves (Phase 3+) — do not start until pilot Grown

`am-portfolio`, `am-oms`, `am-trade-management-service`, `am-analysis`, `am-document-processor`, `am-cloudinary-manager`, `am-email-extractor`, `am-identity`, then remaining enabled catalog.

See [INVENTORY.md](INVENTORY.md) for typed OK / FAILED matrix.

## Grown (program)

- [ ] Phase 0 reviewed / accepted (pilot = am-market)
- [ ] Phase 1 Grown (CI + package identity)
- [ ] Phase 2 Grown (**am-market** SDK + MCP + E2E all green)
- [ ] Phase 3 Grown (next-wave services)
- [ ] Phase 4 Grown (SpecKit + fleet)
- [ ] Phase 5 Grown (**overall 10/10** scorecard green)

## Refuse

- Do not treat thin HTTP stubs as the product SDK
- Do not soft-pass empty `typed/` in CI
- Do not make SpecKit a second OpenAPI SoT (am-specs stays SoT)
- Do not host a second platform MCP server outside `am-core-services/services/am-mcp-server`
- Do not conflate am-mcp-server domain tools with am-specs contract packs (same server, different layers)
- Do not commit registry secrets; Vault refs only
- Do not regenerate **all** SDKs on every PR — only services with respecting contract changes (plus explicit backfill)
- Do not sign off production on contract/payload tests alone — SDK plugins + MCP E2E required ([E2E_PROD.md](E2E_PROD.md))
- Do not use LLMs to generate or “improve” SDKs/MCP packs — contract is enough; generators must stay deterministic
- Do not expand beyond **am-market** until Phase 2 pilot is Grown and tested
