# Phase 5 tests — Cold invent

**Phase:** [../phase-5.md](../phase-5.md)

## Test

- [x] Gate: Phase 0 LLM=**no** → live invent **N/A**
- [x] Cold local onboard (mock chat) → `llm_invoked=true` (≤2 calls)
- [x] Grounding: bad path → status `draft`
- [x] invent_complete true after mocked invent
- [x] Immediate re-onboard → `llm_invoked=false`

## Grown

- [x] Cold once / warm zero proven in unit tests; live LiteLLM invent green

## Evidence

- Units: `test_scenario_bank_invent.py` — typed registry `am.qa.prompts/v1` type=`invent`, cold `call_count=2`, warm skip, draft grounding (missing `expected_status` / ban / security non-2xx), feature export auth+status, onboard LLM-down gate
- Prompt SoT: `qa-agent/prompts/` (platform skill semantics); per-service invent profile + API surface + scenarios + features in **Mongo** (`qa_*` collections), memory backend for unit tests
- LiteLLM `https://litellm.asrax.in` alive; Contabo prod `am-qa-agents-prod-synced-secrets` key works
- Invent path: derive(tools)→DB → LiteLLM invent → `qa_scenarios`/`qa_features` → quality rating in `qa_knowledge`
- Note: OpenAPI still HTML SPA — invent surface = Postman/tools digest in DB (not plugin invent.yaml)
