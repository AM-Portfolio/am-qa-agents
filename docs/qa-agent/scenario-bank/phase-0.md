# Phase 0 — Setup + MCP + LLM probe

**Goal:** Local install + MCP sync + record whether LLM is available. No invent, no pack mutations.

**Prereq:** Read [README.md](README.md) locked decisions.

## Implement

- [x] `pip install -e ".[dev]"` from am-qa-agents root
- [ ] `AM_AGENT_ENV=dev` → `am ai mcp-sync --ide cursor` (operator — after qa-agent restart with new MCP tools)
- [x] Confirm SPT catalog path exists for subscription/identity (catalog-external; live list needs running SPT)
- [x] LiteLLM env: `LITELLM_BASE_URL` + `LITELLM_MASTER_KEY` in `.env` (key present; proxy not reachable from laptop)
- [x] Probe via local `probe_litellm` → **available: no** (see Evidence)
- [ ] Optional spend: `qa_bank_llm_status(ping_chat=true)` once models list OK
- [x] SPT auth env names documented in `.env.example` (no values in git)

## Test

Use [tests/phase-0.md](tests/phase-0.md).

- [ ] `spt_health` JSON ok (needs running qa-agent MCP)
- [x] `probe_litellm` / `qa_bank_llm_status` code → provider=`litellm`; available=no recorded
- [x] Unit: `pytest …/test_scenario_bank_llm_status.py -q` — 3 passed

## Grown

- [x] Phase 0 complete for local track; ready for Phase 1
- [x] LiteLLM available=no → Phase 5 invent blocked in advance (seed path still required)

## Stop if fail

MCP health not JSON / install broken → do not start Phase 1.

## Refuse

- No invent / onboard with LLM
- No Contabo prod mutate
- No secrets in Evidence
