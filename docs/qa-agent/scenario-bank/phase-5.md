# Phase 5 — Cold LLM invent + grounding

**Goal:** Chunked invent ≤2 calls when cold/drift/force; ground steps to tools; set `invent_complete`. Skip entire invent if Phase 0 LLM=no.

**Prereq:** [phase-4.md](phase-4.md) Grown. Phase 0 LLM probe = **yes** (else mark N/A with Evidence).

## Implement

- [x] `scenario_planner` chunked invent via injectable chat / `LiteLLMClient` (`LLM_PLANNER_MODEL`)
- [x] Gate: `probe_litellm()` / `qa_bank_llm_status` available=true
- [x] Invent only if smoke OK + LiteLLM up + (cold | needs_reinvent | force_llm)
- [x] Ungrounded → `draft`; LLM UI → `draft_ui`
- [x] Wire `qa_plugin_onboard` invent path
- [x] Record call count in invent result / knowledge

## Test

Use [tests/phase-5.md](tests/phase-5.md).

- [x] Cold onboard (mocked chat): `llm_invoked=true`, `call_count≤2`
- [x] Immediate second onboard: `llm_invoked=false` (warm)
- [x] Live invent via **Ollama** (LiteLLM proxy 401 / localhost down) — bank filled

## Grown

- [x] Invent path + grounding proven in unit tests
- [x] Live invent (Ollama + Postman/catalog context) — bank 21 / invent_complete

## Stop if fail

Invent without grounding → do not set invent_complete.

## Refuse

- Invent on Contabo prod for L5/security execution
- More than 2 chunked calls per cold invent without plan change
- Invent when smoke blocked
