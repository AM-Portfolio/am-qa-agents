# Phase 7 — Select → prep → execute → report

**Goal:** Select-few (default 6) → prep fail-closed on **dev** → execute runnable → HTML/JSON report with bank coverage advisory. Plugin pack runner (no subscription-only hardcode).

**Prereq:** [phase-6.md](phase-6.md) Grown.

## Implement

- [x] Select-few mix from skills.yaml (`env_policy.select_few` + pack `bank_advisory`)
- [x] Generic `run_api_pack` via plugin runners + prep gate
- [x] Wire `run_subscription_module_complete.py` → pack_runner
- [x] Report: decision, bank coverage, draft_ui backlog, llm_invoked, prep
- [x] MCP `qa_plugin_run_pack`

## Test

Use [tests/phase-7.md](tests/phase-7.md).

- [x] Unit: prep fail-closed skips execute; silent SKIPPED → NO_GO
- [ ] Live: complete script `--skip-ui` on **dev** (needs SPT auth)
- [ ] Live MCP/ops suite=subscription_module (restart Control MCP)

## Grown

- [x] Pack path unit green; refuse silent skip
- [x] Unlocks Phase 8 docs/UI polish

## Stop if fail

Prep fail on **dev** still runs execute → fail-closed broken; stop.

## Refuse

- Silent SKIPPED green
- Full invent inside every pack run
