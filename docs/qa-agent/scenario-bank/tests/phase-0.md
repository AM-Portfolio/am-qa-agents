# Phase 0 tests — Setup + LLM probe

**Phase:** [../phase-0.md](../phase-0.md)

## Test

- [ ] `pip install -e ".[dev]"` succeeds
- [ ] `am ai mcp-sync --ide cursor` with `AM_AGENT_ENV=dev`
- [ ] MCP `spt_health` → JSON ok
- [ ] MCP `spt_list_services` lists subscription/identity (or Evidence: blocked reason)
- [ ] MCP `qa_bank_llm_status` → provider=`litellm`, `available` yes/no, `models_sample`
- [ ] Optional: `qa_bank_llm_status(ping_chat=true)` once
- [ ] `pytest qa-agent/ui_evidence/tests/test_scenario_bank_llm_status.py -q` green

## Grown

- [ ] No invent / pack run during Phase 0 (probe only)

## Evidence

Date · LiteLLM base_url · available · models_count · model id · ping_chat yes/no (no keys).

**2026-10-06 local probe (agent):**

- Unit tests: `test_scenario_bank_llm_status.py` — **3 passed**
- `LITELLM_MASTER_KEY` configured in `qa-agent/.env` (not printed)
- `http://localhost:4000` — connection refused (proxy not running on laptop)
- `https://litellm.asrax.in` — HTTP 401 with local key (use Vault/cluster key or port-forward `am-ai/svc/litellm`)
- MCP tool shipped: `qa_bank_llm_status`
- **available: no** until LiteLLM reachable with a valid key → Phase 5 invent blocked; Phases 1–4 proceed
