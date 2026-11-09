# Service QA plugins — TODOS

SoT plan: [PLAN.md](./PLAN.md). Env name is always **dev** (never dig).  
Phase track (identity-infra-split style): [../scenario-bank/README.md](../scenario-bank/README.md) — this work is **Phase 1**.  
Mark `[x]` only when [../scenario-bank/tests/phase-1.md](../scenario-bank/tests/phase-1.md) Evidence is filled.

## Implementation

- [ ] **plugin-schema-loader** — `am.qa.plugin/v1` schema + [`ui_evidence/plugins/loader.py`](../../../qa-agent/ui_evidence/plugins/loader.py) list/get + fixture tests
- [ ] **mcp-plugin-tools** — FastMCP `qa_plugin_*` (list/get/reload/onboard/catalog/prep/set_enabled) on Control MCP
- [ ] **migrate-subscription-plugin** — [`qa-agent/plugins/am-subscription/`](../../../qa-agent/plugins/) from `subscription_module.yaml`; suite/api_pack via loader; `env=dev`
- [ ] **generic-pack-runner** — Replace release_ops/gateway subscription hardcoding with plugin-driven [`pack_runner.py`](../../../qa-agent/ui_evidence/plugins/pack_runner.py)
- [ ] **prep-bank-hooks** — Plugin `data_prep.entry` + `onboard_plugin` wired to scenario-bank (mutate on **dev**)
- [ ] **identity-thin-plugin** — `qa-agent/plugins/am-identity/` login/JWT + auth API catalog
- [ ] **plugin-docs-contracts** — Authoring README + CONTRACTS + MCP tool list; draw.io Containers note (**dev** not dig)
- [ ] **tests-all** — Unit/parity: loader, MCP registration, subscription catalog parity, env normalize dig→dev

## Started in tree (partial)

| Path | Role |
|------|------|
| [qa-plugin.schema.json](../schemas/qa-plugin.schema.json) | Manifest schema |
| [ui_evidence/plugins/](../../../qa-agent/ui_evidence/plugins/) | loader / pack_runner / onboard |
| [scenario_bank/skills.yaml](../../../qa-agent/ui_evidence/scenario_bank/skills.yaml) | Shared skill taxonomy |

## Exit criteria

1. `qa_plugin_list` returns `am-subscription` + `am-identity` with `enabled: true`.
2. ops/start with `suite=subscription_module` resolves `api_pack` from plugin (no gateway hardcode).
3. Detach: `qa_plugin_set_enabled(am-subscription, false)` hides suite from list.
4. Pytest for loader + subscription parity green.
