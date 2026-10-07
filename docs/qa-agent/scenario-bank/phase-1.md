# Phase 1 — Service plugins (plug / detach)

**Goal:** Discoverable `am.qa.plugin/v1` plugins for subscription + identity; MCP `qa_plugin_*`; no release_ops hardcode for api_pack default.

**Prereq:** [phase-0.md](phase-0.md) Grown. Design: [../plugins/PLAN.md](../plugins/PLAN.md).

## Implement

- [x] Schema [../schemas/qa-plugin.schema.json](../schemas/qa-plugin.schema.json)
- [x] Loader [`ui_evidence/plugins/loader.py`](../../../qa-agent/ui_evidence/plugins/loader.py)
- [x] `qa-agent/plugins/am-subscription/` + `am-identity/` with `plugin.yaml`
- [x] MCP tools: list / get / reload / catalog / set_enabled / onboard / prep (+ `qa_bank_llm_status`)
- [x] Gateway / ops resolve api_pack from plugin suite (`resolve_api_pack_default`)
- [x] Unit tests + live plugins (`test_plugin_loader.py`)
- [x] Env normalize: input `dig` → **dev**

## Test

Use [tests/phase-1.md](tests/phase-1.md).

- [x] Local list shows both enabled
- [x] Detach/reattach via `set_plugin_enabled`
- [ ] Live MCP after qa-agent restart

## Grown

- [x] Plug/detach without editing core Python for new service folder
- [x] Unlocks Phase 2 onboard against a real plugin id

## Stop if fail

Loader cannot list plugins → do not start smoke/onboard.

## Refuse

- Hardcoding `api_pack=subscription` when suite matches (use plugin)
- Rewriting hand-authored `plugin.yaml` comments for enable (use `plugin.state.yaml`)
