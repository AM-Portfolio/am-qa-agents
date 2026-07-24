# qa-agent — design package

**One folder** for ReleaseReadiness / QA gate design SoT (mirrors [`docs/agent-platform/`](../../am-agents/docs/agent-platform/)).

| File | Role |
|------|------|
| [QA_AGENT_PLAN.md](QA_AGENT_PLAN.md) | Full design spec (§1–§24) |
| [UPCOMING_WORK_AND_TEST.md](UPCOMING_WORK_AND_TEST.md) | Pilot handoff + test plan |
| [AGENTS_OWNERSHIP_AND_DONT.md](AGENTS_OWNERSHIP_AND_DONT.md) | Who owns what · do / don’t across agents |
| [TASKS.md](TASKS.md) | Page-wise task plan |
| [MATRIX_RANKER.md](MATRIX_RANKER.md) | §23.3 ranker note |
| **[qa-agent.drawio](qa-agent.drawio)** | **Multi-page Draw.io** |
| [sheets/](sheets/) | Mermaid sources for each Draw.io page |
| [schemas/](schemas/) | JSON Schema appendix (§23.4) ✅ |
| [decisions/](decisions/) | ADR-QA-001..004 ✅ |
| [../config/examples/](../config/examples/) | Sample YAMLs (§23.5) ✅ |

## Status

**Draw.io + Batch D + Code Phases 0–4 complete.**

## Draw.io pages (9)

1. **Four Layers**
2. **Module Owns / Not**
3. **ReleaseReadiness E2E**
4. **GitNexus Sync + Fallback**
5. **Specialists**
6. **LoadContext + Handoff**
7. **Verify + Publish**
8. **Automation map**
9. **Phases 0–4**

## Reference pattern

Clone [support-agent](../../am-agents/support-agent/) orchestration + [agent-platform.drawio](../../am-agents/docs/agent-platform/agent-platform.drawio) diagram style.
