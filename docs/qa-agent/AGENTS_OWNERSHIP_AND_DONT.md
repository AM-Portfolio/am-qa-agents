# Agents ownership — do / don’t (many agents around)

Last updated: **2026-07-22**  
Companion: [UPCOMING_WORK_AND_TEST.md](UPCOMING_WORK_AND_TEST.md) · Plan: [QA_AGENT_PLAN.md](QA_AGENT_PLAN.md)

**One line:** **qa-agent = conductor.** Specialists in **am-agents** = band. **core-services** = Asrax domain. Don’t make the conductor play every instrument, and don’t build a second conductor in am-agents.

---

## 1. Who owns what

| Layer | Owner | Job |
|-------|--------|-----|
| Release / change gate | **qa-agent** (this repo) | Temporal release-readiness, LoadContext, matrix, dossier, HITL, GitHub check |
| Ops / incident stream | **support-agent** | Route, analyze, verify, HITL for broader support — not the same as release-readiness |
| UI regression | **ui-test-agent** | Playwright, baselines, auth walks |
| API functional / meta | **fin-api-testing-agent** | OpenAPI discover, single/batch test, meta dashboard |
| Load / SPT | **tool-agent** `spt` (+ **k6**) | Catalog selectors → load runs |
| Platform / network probes | **tool-agent** plugins | observe, kafka, redis, postgres, vault, document… |
| DB / query | **db-agent** | plan/execute data plane |
| Portfolio chat UX | **fin-portfolio-agent** | NL chat → REST to analysis (thin client) |
| Domain truth (money/data) | **am-core-services** + **am-mcp-server** | analysis, trade, market, auth… + MCP tools |
| Shared “what to test” | **am-agents/catalog/** (`spt/`, `verify/`, prompts) | Targets/flows — code must not hardcode service names |
| Secrets | **Vault** | Never in RunStore / Git / LLM |
| Run ledger | **RunStore** (Postgres) | Latest pass/fail/skip per run/step |
| Artifacts | **MinIO** via tool-agent `document` | PDF, screenshots, k6 reports (`result_ref`) |
| Infra dashboards | **Grafana** (am-obs-platform) | CPU/errors/SLO — do not rebuild in qa-agent |

Hard rule (plan): **orchestrator only — no duplication of fin-agent, ui-test-agent, or tool-agent logic.**

---

## 2. What is already duplicate / temporary extra

| Extra today | Why it exists | End state |
|-------------|---------------|-----------|
| qa-agent `adapters/api_load.py` | SPT k6 still stub | Prefer `spt.execute`; keep api_load as **backup only** |
| qa `config/environments.yaml` + `load-rules.yaml` | Pilot LoadContext | Converge targets toward **`catalog/spt`** (+ env overlays) |
| Nested `am-agents/qa-agent/` | Accidental / leftover | Ignore or delete; **this standalone repo** is SoT |
| Postman / Requestly as “agent load runner” | Human/MCP explore | Postman = authoring only; agent runs **catalog → SPT → k6** |
| Merging ui-test + api-test into one agent | Tempting “one test agent” | **Don’t** — one medium per specialist; qa composes them |
| Mega “test agent” inside am-agents | Second orchestrator | **Don’t** — that is qa-agent’s job |

---

## 3. DO

- **DO** call specialists (HTTP / tool-agent plan-execute / support adapters); don’t reimplement them in qa-agent.
- **DO** put reusable load/verify targets in **`am-agents/catalog/spt/`** (and verify catalogs).
- **DO** keep ui-test and api-test **separate**; compose both from qa (or support) workflows.
- **DO** keep Asrax domain in **core-services / MCP**; agents consume, they don’t own domain truth.
- **DO** record outcomes in **RunStore**; files in **MinIO**; watch infra in **Grafana**.
- **DO** use LLM to **select** scenarios / summarize — not to invent prod load scripts every run.
- **DO** finish **real SPT k6**, then flip qa to prefer it over direct `api_load`.
- **DO** use honest modes: `live` | `fallback_*` | `skipped` (no fake COMPLETED).
- **DO** treat support-agent and qa-agent as **different streams** (incident vs release gate).

---

## 4. DON’T

- **DON’T** add Playwright, MetaEngine, k6 engine, or Grafana scrape logic inside qa-agent.
- **DON’T** add a second release-readiness Temporal product inside am-agents “like qa-agent”.
- **DON’T** merge **ui-test** and **api-test** into one deployable agent.
- **DON’T** turn **fin-api-testing** into the load engine (that is SPT/k6).
- **DON’T** turn **fin-portfolio** chat into the QA gate or the API test harness.
- **DON’T** make **Postman / Requestly / Newman** the production agent load path.
- **DON’T** put secrets in catalog git, RunStore rows, or LLM prompts.
- **DON’T** hardcode prod service names in worker/ports code — use catalog ids/tags/selectors.
- **DON’T** maintain two qa-agent trees (standalone + nested under am-agents).
- **DON’T** duplicate Grafana dashboard YAML in am-agents or qa-agent.
- **DON’T** delete tool / db / ui-test agents when “cleaning up” platform — compose them.

---

## 5. Configure → agent runs (load)

```
Edit catalog/spt/services + flows   (+ Vault for URLs/secrets)
        ↓
qa-agent / support selects tags/ids (optional LLM)
        ↓
tool-agent SPT execute → k6
        ↓
RunStore + Grafana + dossier
```

Empty selector = fatal (ADR-004). Postman stays for humans / Cursor MCP sync (`npm run postman:sync`) — not the SPT runtime.

---

## 6. Quick map when you’re lost

```
Need release gate / dossier?     → qa-agent
Need browser test?               → ui-test-agent
Need OpenAPI functional test?    → fin-api-testing-agent
Need load / performance?         → tool-agent SPT + catalog/spt
Need metrics during test?        → tool-agent observe → Grafana
Need portfolio “how’s my money?” → fin-portfolio / am-mcp (domain)
Need incident / multi-specialist ops? → support-agent
```

---

## 7. Link to next work

Pilot gaps, test plan T1–T18, and P0–P3 blockers live in **[UPCOMING_WORK_AND_TEST.md](UPCOMING_WORK_AND_TEST.md)**.

Priority that reduces duplication first:

1. Vault + ui-test live (stop skip theater)  
2. Grafana observe live  
3. SPT k6 real → demote `api_load` from source-of-truth  
4. Align LoadContext targets with `catalog/spt`  
5. Remove nested / confusion paths (nested qa-agent folder, fake COMPLETED)
