# Phase 2 — Skills + knowledge + contract smoke

**Goal:** Persist knowledge + `openapi_hash`; contract smoke gates invent; smoke fail → `onboard_blocked`, zero LLM.

**Prereq:** [phase-1.md](phase-1.md) Grown.

## Implement

- [x] Platform [`skills.yaml`](../../../qa-agent/ui_evidence/scenario_bank/skills.yaml) locked
- [x] Knowledge write under `ui_evidence/data/scenario_bank/knowledge/`
- [x] Contract smoke: tool count ≥ `min_tools` (empty → blocked)
- [x] `qa_plugin_onboard` / `onboard_plugin` wires smoke (invent deferred Phase 5)
- [x] Unit: empty tools → blocked; ok writes knowledge; `llm_invoked=false`

## Test

Use [tests/phase-2.md](tests/phase-2.md).

- [x] Local onboard with mocks records smoke + knowledge
- [x] Fail path never sets `llm_invoked=true`
- [ ] Live MCP onboard on **dev** (needs SPT + restarted qa-agent)

## Grown

- [x] Knowledge artifact path proven in unit test
- [x] Unlocks Phase 3 prep (seed always allowed)

## Stop if fail

Cannot distinguish HTML vs JSON OpenAPI → fix before invent (Phase 5).

## Refuse

- Calling LLM when smoke fails
- Skipping knowledge persist
