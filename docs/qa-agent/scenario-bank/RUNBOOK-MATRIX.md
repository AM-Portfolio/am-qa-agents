# Scenario bank — runbook matrix

Maps phase → local command → MCP tools. Prefer CI/local pytest; MCP for live **dev** proof.

| Phase | Local | MCP (Control / qa-agent) | Grown signal |
|-------|-------|--------------------------|--------------|
| 0 Setup | `pytest …/test_scenario_bank_llm_status.py` | `spt_health`, `qa_bank_llm_status` (LiteLLM) | LiteLLM available yes/no recorded |
| 1 Plugins | `pytest …/test_plugin_*.py` | `qa_plugin_list`, `get`, `reload`, `set_enabled`, `catalog` | Both plugins listed; detach works |
| 2 Smoke | unit HTML/JSON fixtures | `qa_plugin_onboard` env=dev | knowledge file; blocked⇒no LLM |
| 3 Prep | unit seed + optional live | `qa_plugin_prep` env=dev | fail-closed unit green |
| 4 Bank | unit cap/lock/dedupe | `qa_plugin_catalog` / bank list | seed rows without invent |
| 5 Invent | cold onboard once | `qa_plugin_onboard` (LLM on) | `llm_invoked` once then warm false |
| 6 Warm | two warm packs | onboard/pack env=dev and prod | zero LLM; L5 blocked on prod |
| 7 Pack | `run_subscription_module_complete.py --skip-ui` | ops/start suite=subscription_module | GO or clear NO_GO |
| 8 Docs/UI | grep dig; optional UI suite | `ui_test_list_profiles` | docs say **dev**; SUB_UI_* listed |

## Env × skill policy

| Env | data_generator | happy/L2 | L5 / security | mutate grant |
|-----|----------------|----------|---------------|--------------|
| **dev** | run / fail-closed | run | run | allowed if tools exist |
| Contabo prod | assert-only | run | **block** | **never** |

## Break-glass

| Prefer | Break-glass |
|--------|-------------|
| pytest + complete script | Live MCP prep/onboard against **dev** |
| ops/start via GHA | Manual gateway POST with token (never commit token) |
