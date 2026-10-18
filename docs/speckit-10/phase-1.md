# Phase 1 — CI gates + package identity (A0–A1)

**Goal:** CI and validate require enterprise typed SDKs; package coords/docs locked. Score: **CI gate → 10**, docs → ~9.

**Prereq:** [phase-0.md](phase-0.md) Grown.

**Repos:** am-specs

## Implement

- [x] Pin `@openapitools/openapi-generator-cli` (or jar) in am-specs CI; fail if missing
- [x] Add `generate_sdk.py --require-typed` (fail-hard); fix `openapi_codegen.py` soft-ok
- [x] `assert_sdk_layout` / validate: non-empty `typed/{java,python,dart}` for SpecKit pilot allowlist
- [x] **Change-driven pipeline skeleton** ([PIPELINE.md](PIPELINE.md)): `detect_changed_services.py` + `sdk-changed.yml` generate-changed matrix
- [x] Keep `workflow_dispatch` force path: single `service=` or rare `all_enabled=true` backfill
- [ ] Normalize layout: `typed/` primary + facade auth/config naming polish (`facade/` rename optional later)
- [x] Update ENABLEMENT + SCORECARD: enterprise SDK required (retire “never --sdk” for this track)
- [x] Update CONSUMING_ASRAX for enterprise typed path
- [x] Product facets: `services/<id>/grouping.yaml` → SDK `Service.group()` + MCP `groups.json` (one package, not many SDKs)

## Test

Use [tests/phase-1.md](tests/phase-1.md) + [VERIFY.md](VERIFY.md) (GitHub MCP).

- [ ] CI installs generator; validate green on PR (after pilot generate committed)
- [ ] `--require-typed` fails without generator / empty typed
- [ ] PR that only touches `services/<id>/openapi.yaml` schedules generate for that id only (GitHub MCP job logs)
- [x] Docs no longer contradict catalog

## Grown

- [x] Phase 1 gates + change-driven skeleton landed; pilot typed packs generated — next: CI PR green + Phase 2 E2E

## Stop if fail

Generator cannot run in CI → do not mass-generate.

## Refuse

- No silent thin fallback for focus/enabled
- No publishing to Maven/PyPI yet (Phase 5)
