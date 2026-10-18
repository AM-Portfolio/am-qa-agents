# SpecKit — change-driven SDK / MCP pipeline

**Locked rule:** Pipelines regenerate enterprise SDKs (and related MCP tools) **only for services whose contract changed** — not the whole fleet on every push.

## What counts as a “respecting change”

A service id is in the **regen set** when the PR/push touches any of:

| Path pattern | Meaning |
|--------------|---------|
| `services/<id>/openapi.yaml` | Contract body changed |
| `services/<id>/openapi.json` | Same |
| `services/<id>/meta.yaml` | Version / enablement metadata that affects packs |
| `services/<id>/aliases.yaml` | Glossary overlays affecting generated APIs |
| Explicit workflow input `service=` | Manual force (sync-dev / SpecKit button) |

**Not** a per-service regen trigger alone:

- Unrelated docs / catalog-only comment tweaks (unless `catalog/services.yaml` adds/enables a new id → that id only)
- Generator script changes → optional **full** or **matrix of previously enabled** rebuild (separate job, not default PR path)

## Pipeline jobs (am-specs)

```text
detect-changed-services
  → list service ids from git diff (base...HEAD)
validate (all enabled layouts — cheap)
  → typed layout must already exist for every enabled (no empty typed)
generate-changed (only regen set)
  → for each id: generate_mcp_tools + generate_sdk --lang all --require-typed
  → **never commit `sdks/`** — upload CI artifacts only
build-changed
  → mvn/python/dart compile/import smoke **only** for regen set
e2e-changed (SpecKit / qa-agent job)
  → contract Try + Java/Python/Dart SDK plugins + MCP pack tools ([E2E_PROD.md](E2E_PROD.md))
  → **only** for regen set; fail closed → no publish
publish-changed (Phase 5 / tags)
  → publish Maven/PyPI/pub **only** for regen set **after** e2e-changed green
```

**Local before CI:** `python scripts/verify_local.py` (generate → smoke → pack under gitignored `sdks/` + `dist/`).
```

### detect-changed-services (sketch)

```bash
# vs origin/main (or PR base)
git diff --name-only origin/main...HEAD \
  | sed -n 's|^services/\([^/]*\)/.*|\1|p' \
  | sort -u
```

Empty set → skip generate/build/publish jobs (validate still runs).

### Force / backfill

| Mode | When |
|------|------|
| `workflow_dispatch` + `service=<id>` | One service (today’s sync-dev pattern) |
| `workflow_dispatch` + `all_enabled=true` | Phase 2/3 backfill or generator major bump |
| SpecKit “Generate SDK” | Passes single service id into am-specs workflow |

## GitHub MCP verify

For a PR that only changes `services/am-portfolio/openapi.yaml`:

1. GitHub MCP: confirm generate/build jobs ran for **`am-portfolio` only** (log matrix).
2. Confirm other services’ `sdks/` **not** rewritten in the diff (or only if meta/global template forced).
3. validate still green for full enabled layout.
4. If publish job runs on tag: only portfolio package version bumped.

## Phase mapping

| Phase | Pipeline behavior |
|-------|-------------------|
| 1 | Add detect + generate-changed skeleton; validate requires typed present |
| 2–3 | Backfill once with `all_enabled` / focus list; afterward PRs are change-driven |
| 4 | SpecKit triggers workflow with **one** service id |
| 5 | Publish job publishes **only** changed service packages |

## Refuse

- Default PR path that runs `generate_sdk --all-enabled` every time
- Publishing every package on every release tag without a change filter
