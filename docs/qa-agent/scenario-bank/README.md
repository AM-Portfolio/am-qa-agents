# LLM scenario bank + service plugins (delta track)

Phase track for QA scenario bank and loosely coupled **service plugins**.  
Design SoT: [PLAN.md](./PLAN.md) · Plugins design: [../plugins/PLAN.md](../plugins/PLAN.md) · Diagram: [architecture.drawio](./architecture.drawio)

Index: [../README.md](../README.md) · Schema: [../schemas/qa-plugin.schema.json](../schemas/qa-plugin.schema.json)  
Operator matrix: [RUNBOOK-MATRIX.md](./RUNBOOK-MATRIX.md) · Todos pointer: [TODOS.md](./TODOS.md)

## Recommendation (locked)

**One service = one plugin folder** under `qa-agent/plugins/<id>/`. Platform core discovers manifests; invent/bank/select are core. Env name is always **dev** (never dig). Contabo prod = happy / L2 / assert-only — no mutate, no L5/security execute.

**LLM:** invent only on cold / `needs_reinvent` / `force_llm`. Warm + `invent_complete` = **zero LLM**. Contract smoke fail = no invent (seed-only ok).

## Locked decisions

| Item | Value |
|------|--------|
| Env mutate / L5 / fail-closed prep | **dev** only |
| Contabo prod | read-only / assert-only; block `level5_abuse`, `security`, grant/ensure |
| Plugin root | `qa-agent/plugins/<service_id>/` + `plugin.yaml` (`am.qa.plugin/v1`) |
| SPT / swagger | Product `spt.yaml` + catalog-external; plugin references `spt_service_id` |
| Bank cap | 200 / `(service, env)` |
| First plugins | `am-subscription`, `am-identity` |
| LLM | **LiteLLM** proxy (`LITELLM_BASE_URL` + `LITELLM_MASTER_KEY`); invent via existing `ui_evidence.llm.LiteLLMClient` |
| MCP | `qa_bank_llm_status`, `qa_bank_list`, `qa_bank_select`, `qa_plugin_*`, `qa_plugin_run_pack` (+ `spt_*`) |
| Verify style | Same loop as identity-infra-split: Prereq → Implement → Test → Grown |

## Phase map

| Order | Phase | File | Tests |
|-------|-------|------|-------|
| 0 | Setup + MCP + LLM probe | [phase-0.md](phase-0.md) | [tests/phase-0.md](tests/phase-0.md) |
| 1 | Service plugins (plug/detach) | [phase-1.md](phase-1.md) | [tests/phase-1.md](tests/phase-1.md) |
| 2 | Skills + knowledge + contract smoke | [phase-2.md](phase-2.md) | [tests/phase-2.md](tests/phase-2.md) |
| 3 | Hand-seeded data_prep (**dev**) | [phase-3.md](phase-3.md) | [tests/phase-3.md](tests/phase-3.md) |
| 4 | Bank store + invent lock | [phase-4.md](phase-4.md) | [tests/phase-4.md](tests/phase-4.md) |
| 5 | Cold LLM invent + grounding | [phase-5.md](phase-5.md) | [tests/phase-5.md](tests/phase-5.md) |
| 6 | Warm path + env policy | [phase-6.md](phase-6.md) | [tests/phase-6.md](tests/phase-6.md) |
| 7 | Select → prep → execute → report | [phase-7.md](phase-7.md) | [tests/phase-7.md](tests/phase-7.md) |
| 8 | Features + draft_ui + docs | [phase-8.md](phase-8.md) | [tests/phase-8.md](tests/phase-8.md) |

## Loop

```text
Prereq → Implement → am ai mcp-sync (when MCP tools change) → Test (tests/phase-N) → Grown → next
```

**Local first, then MCP.** Fill **Evidence** in `tests/phase-N.md` (no secrets).

**Track status (2026-10-06):** Phases 0–8 Grown locally (unit Evidence). Phase 5 live LiteLLM invent = N/A (proxy unavailable). Live MCP tools need Control MCP restart + `am ai mcp-sync`.

## Refuse (whole track)

- Saying **dig** in docs/code for this feature (use **dev**)
- LLM invent when contract smoke fails
- Contabo prod mutate / L5 / security / grant ensure
- Hardcoding new services in `release_ops` / gateway (use plugins)
- Auto Playwright builders from LLM in v1
- Committing SPT passwords, tokens, or LLM keys
- Starting Phase N+1 before Phase N **Grown**
- Skipping LLM probe in Phase 0 (must record available yes/no)
