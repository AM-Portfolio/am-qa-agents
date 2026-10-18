# SpecKit 10/10 — Verify with GitHub MCP / CI

**Rule:** A phase is not Grown until **GitHub CI** on `AM-Portfolio/am-specs` (and SpecKit PRs on `am-qa-agents` where relevant) is green **and** the checklists below pass. Do not claim SDK/MCP/publish done from local-only runs.

## Tools (use these)

| Tooling | Use for |
|---------|---------|
| **GitHub MCP** (Asrax Hub / `am-mcp` GitHub) | List workflow runs, PR checks, artifacts, releases/packages |
| `gh` CLI (fallback) | `gh run list/watch`, `gh pr checks`, `gh api` |
| Local (optional smoke) | `mvn` / `python` / `dart` — never replaces CI |

### GitHub MCP verify loop (every phase that opens a PR)

1. Open / identify PR on `AM-Portfolio/am-specs` (and `am-qa-agents` for Phase 4+).
2. Via GitHub MCP: list checks / workflow runs for that PR head SHA.
3. Require these am-specs workflows green (names may match `.github/workflows/`):
   - `validate.yml` (must include openapi-generator + typed layout after Phase 1)
   - `sync-dev.yml` when harvest/enable is in scope
   - `release-pack.yml` (or successor) when publish/pack is in scope
4. Download / inspect artifacts: `dist/contracts-v*` must include OpenAPI + `tools.json` + **`sdks/`** (after Phase 2).
5. Record run URL + conclusion in the phase Test checklist.

### Per-service proof (Phases 2–3)

For **each** service id under test:

| Check | Pass criteria |
|-------|----------------|
| OpenAPI | `services/<id>/openapi.yaml` present in PR |
| MCP | `services/<id>/tools.json` + `packages/mcp/services/<id>/` (or index entry) |
| Typed Java | `sdks/<id>/typed/java/` non-empty; CI or job compiles |
| Typed Python | `sdks/<id>/typed/python/` non-empty; import smoke in CI |
| Typed Dart | `sdks/<id>/typed/dart/` non-empty; analyze in CI |
| TYPED.md | OK (not FAILED) |
| Package coords | `com.asrax` / `asrax-<slug>` / version from meta (not `org.openapitools:openapi-java-client`) |

Maintain a **service matrix** copy in the PR description or update [INVENTORY.md](INVENTORY.md).

### Production E2E proof (Phases 4–5)

Per [E2E_PROD.md](E2E_PROD.md), for each service in the change set (GitHub MCP + SpecKit report):

- [ ] Contract Try / working payloads green on target env  
- [ ] Java SDK plugin E2E green  
- [ ] Python SDK plugin E2E green  
- [ ] Dart SDK plugin E2E green  
- [ ] MCP pack tools invoke green (not list-only)  
- [ ] Single go/no-go artifact attached to workflow run  

### Publish proof (Phase 5)

| Check | Pass criteria |
|-------|----------------|
| Pack | `release-pack` (or publish) workflow green; artifact has sdks |
| Maven | Package visible in GH Packages (or configured registry) for sample service |
| Python | Wheel/sdist published or dry-run log with version |
| Dart | pub publish dry-run or GH-hosted package evidence |
| Secrets | Only Vault/GitHub Actions secrets — nothing in git |

## Repos

| Repo | Workflows |
|------|-----------|
| `AM-Portfolio/am-specs` | validate, sync-dev, release-pack (+ future sdk-build / publish / scorecard) |
| `AM-Portfolio/am-qa-agents` | qa-agent / deploy (Phase 4 SpecKit surface) |

## Change-driven proof (required after Phase 1)

See [PIPELINE.md](PIPELINE.md).

- [ ] PR that only changes `services/<id>/openapi.yaml` → GitHub MCP shows generate/build for **that id only**
- [ ] Diff does not mass-rewrite other services’ `sdks/`
- [ ] Full-fleet generate only via explicit backfill / `workflow_dispatch all_enabled`

## Fail closed

- Red CI → phase not Grown  
- Empty typed/ with green validate → Phase 1 incomplete (fix gate)  
- Pack without sdks/ → Phase 2 incomplete  
- Local-only generate without PR/CI → not verified  
- Default pipeline regenerating all SDKs every PR → Phase 1 incomplete  

