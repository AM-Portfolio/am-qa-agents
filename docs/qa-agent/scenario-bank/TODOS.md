# Scenario bank — TODOS

**Hub (phase map):** [README.md](./README.md)  
**Design:** [PLAN.md](./PLAN.md) · **Matrix:** [RUNBOOK-MATRIX.md](./RUNBOOK-MATRIX.md) · **Diagram:** [architecture.drawio](./architecture.drawio)

Same shape as [identity-infra-split](../../../../am-infra-automation/docs/kind-fleet-clusters/identity-infra-split/README.md):

```text
Prereq → Implement → mcp-sync → Test (tests/phase-N) → Grown → next
```

Mark Grown only in `phase-N.md` / `tests/phase-N.md` after local + MCP Evidence.

| Phase | File | Focus |
|-------|------|--------|
| 0 | [phase-0.md](phase-0.md) | Setup, MCP, **LLM available?** |
| 1 | [phase-1.md](phase-1.md) | Plugins plug/detach + `qa_plugin_*` |
| 2 | [phase-2.md](phase-2.md) | Contract smoke + knowledge |
| 3 | [phase-3.md](phase-3.md) | Hand-seeded prep (**dev**) |
| 4 | [phase-4.md](phase-4.md) | Bank store + lock |
| 5 | [phase-5.md](phase-5.md) | Cold LLM invent (or N/A) |
| 6 | [phase-6.md](phase-6.md) | Warm zero-LLM + env policy |
| 7 | [phase-7.md](phase-7.md) | Select → prep → execute → report |
| 8 | [phase-8.md](phase-8.md) | Features + docs |

Tests: [`tests/`](tests/).

Legacy single-file tables moved into phases; do not track work only here.
