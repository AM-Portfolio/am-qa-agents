# Phase 4 — SpecKit orchestrator + prod E2E harness (B)

**Goal:** SpecKit configures projects, drives am-specs generate/PR, prefers snapshots, serves contract MCP packs, and runs **production E2E**: contract + **Java/Python/Dart SDK plugins** + **MCP pack tools**. Score: SpecKit orch **10**, prod E2E → **8**.

**Prereq:** [phase-3.md](phase-3.md) Grown (or Phase 2 Grown if fleet deferred by operator).

**Owner:** **am-qa-agents** (SpecKit). Generators remain in am-specs.

## Implement

- [ ] Branding: portal title/copy → SpecKit (keep `spt_*` / Helm ids internal)
- [ ] Snapshot-first: load `am-specs/services/<id>/openapi.yaml` before live Swagger
- [ ] Control tools/API: sync → `--require-typed` generate → MCP assemble → open PR on am-specs (**one service id** per action)
- [ ] Load/list/call contract tools from am-specs `packages/mcp/`
- [ ] Document split: am-mcp-server = domain enrich; packs = contract MCP
- [ ] **E2E harness** per [E2E_PROD.md](E2E_PROD.md):
  - [ ] Contract Try / working payloads (existing Specs path)
  - [ ] Plugin runners: **Java**, **Python**, **Dart** against generated/published SDKs
  - [ ] MCP pack tool runner (invoke tools, not list-only)
  - [ ] Single go/no-go report in portal + CI artifact
- [ ] Wire change-driven CI: after generate-changed, run E2E **only** for that service set
- [ ] Product docs: configure → generate → **prove production** → publish

## Test

Use [tests/phase-4.md](tests/phase-4.md) + [VERIFY.md](VERIFY.md).

- [ ] Portal SpecKit branding
- [ ] Snapshot preferred when pack present
- [ ] Generate one service id only
- [ ] Pack MCP tools listable **and** invokable
- [ ] For one focus service: contract + Java + Python + Dart + MCP E2E all green (GitHub MCP / SpecKit report)

## Grown

- [ ] SpecKit orch + E2E harness green; ready for publish gate (Phase 5)

## Stop if fail

Cannot reach am-specs / env auth → fix before claiming E2E done.

## Refuse

- Do not reimplement generate_sdk inside qa-agent
- Do not treat payload-only Try as production sign-off
- Do not skip SDK or MCP E2E without SCORECARD exception
