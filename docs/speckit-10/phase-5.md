# Phase 5 — Publish + agents + 10/10 proof (C–E)

**Goal:** Registry publish (Asrax + tenant dry-run), agents/core MCP on packs/generated Java SDKs, CI scorecard proves **overall 10/10**.

**Prereq:** [phase-4.md](phase-4.md) Grown.

**Owner:** SpecKit (orch + UX) · am-specs (publish CI) · am-mcp-server (consume Java SDKs).

## Implement

### C — Publish

- [x] Asrax pilots early: Java → GH Packages Maven; Python + Dart → GH Packages as Maven-hosted `.whl` / `.tar.gz` (no PyPI/pub.dev — GitHub has no those registries). Script: `am-specs/scripts/publish_github_packages.py`; gate: E2E exit 0 on `sdk-changed` (push/dispatch, not PR).
- [ ] Version from contract meta; CI on tag / release-pack (today: `contract_version-ci.<run_number>`)
- [ ] **Publish only changed services** (same detect-changed set as generate) — not every package every release
- [ ] Tenant profile YAML (Maven/PyPI/pub Vault refs); SpecKit dry-run for sample tenant

### D — Agents / core MCP

- [ ] Asrax agents + Cursor use pack-backed contract MCP
- [ ] am-mcp-server uses generated Java enterprise SDK for focus callees
- [ ] Prepare MCP stays on am-mcp-server for domain enrich (documented)

### E — Proof / production go

- [ ] CI job `speckit-scorecard` asserts all dimensions including **Prod E2E**
- [ ] Demo: SpecKit configure → generate → **contract + Java/Python/Dart SDK + MCP E2E** → publish dry-run ([E2E_PROD.md](E2E_PROD.md))
- [ ] Publish blocked unless E2E go for that service change set
- [ ] Update [INVENTORY.md](INVENTORY.md) + [README.md](README.md) scores to **10/10**

## Test

Use [tests/phase-5.md](tests/phase-5.md).

- [ ] Publish dry-run succeeds for Asrax profile (**changed services only**)
- [ ] E2E go recorded for sample service (all surfaces)
- [ ] Tenant profile dry-run documented
- [ ] Scorecard CI green; README overall **10.0**; Prod E2E dimension **10**

## Grown

- [ ] **Program complete — SpecKit readiness 10/10**

## Stop if fail

Registry secrets missing → use Vault refs; do not commit credentials.

## Refuse

- No Maven Central secrets in git
- No claiming 10/10 without scorecard CI green
