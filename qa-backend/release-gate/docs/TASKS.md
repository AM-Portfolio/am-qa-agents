# qa-agent — page-wise task plan

**Status:** Draw.io package **done** · Batch D **done** · Code Phases 0–4 **done**  
**Repo:** standalone `qa-agent/` (outside `am-agents`)  
**Parent:** [QA_AGENT_PLAN.md](QA_AGENT_PLAN.md) · Style ref: [agent-platform.drawio](../../am-agents/docs/agent-platform/agent-platform.drawio)  
**Last updated:** 2026-07-21

---

## Approval gate

| Step | Owner | Status |
|------|-------|--------|
| Review Draw.io package | You | **ready for review** |
| Draw.io pages 0–7 | Agent | **done** |
| Batch D configs/schemas/ADRs | Agent | **done** |
| Code Phases 0–4 | Agent | **done** |

**Out of scope until a later phase:** Python package, Temporal worker, Helm, git commit (unless you ask).

---

## Deliverable tree

```
qa-agent/
  docs/
    README.md                 ✅
    QA_AGENT_PLAN.md          ✅
    TASKS.md                  ✅
    MATRIX_RANKER.md          ✅
    qa-agent.drawio           ✅ 9 pages
    sheets/*.mmd              ✅ 9 files
    schemas/                  ✅ batch D
    decisions/                ✅ batch D
  config/examples/            ✅ batch D
```

---

## Page 0 — Package scaffold (prerequisite)

**Goal:** Folder + index wired; no Draw.io yet.

| # | Task | Output | Deps |
|---|------|--------|------|
| 0.1 | Create `docs/sheets/`, `docs/schemas/`, `docs/decisions/`, `config/examples/` | empty folders ready | — |
| 0.2 | Link TASKS.md + §23–§24 from [README.md](README.md) | index updated | 0.1 |
| 0.3 | Cross-link TASKS.md from QA_AGENT_PLAN §3.8 | already linked; verify | 0.2 |

**Done when:** README lists TASKS + new folders; sheets/schemas/examples dirs exist.

---

## Page 1 — Four Layers

**Draw.io page name:** `Four Layers`  
**Analogue:** agent-platform → Four Layers  
**Mermaid source:** `sheets/four-layers.mmd`

| # | Task | Detail |
|---|------|--------|
| 1.1 | Write `sheets/four-layers.mmd` | L1 Triggers → L2 Edge thin → L3 Temporal → L4 Ports → L5 Specialists |
| 1.2 | Add Draw.io page **Four Layers** | Swimlanes: Triggers · Edge QA Ops thin · Orchestration Temporal · Ports core · Providers specialists |
| 1.3 | Box labels (L1) | `GitHub push/PR` · `CI workflow_run` · `POST /v2/workflows/release-readiness` · `nightly main` |
| 1.4 | Box labels (L2) | `StartWorkflow / SignalWorkflow only` · `Ledger: tracking_id · sha · env · workflow_id` |
| 1.5 | Box labels (L3) | `ReleaseReadinessWorkflow` · `Activities → adapters only` · `intelligence_gate` · HITL |
| 1.6 | Box labels (L4) | `Intelligence` · `EpisodeStore` · `CatalogReader` · `A2A registry` · `WorkflowLedger ★` |
| 1.7 | Box labels (L5) | `GitNexus MCP` · `fin-agent` · `ui-test-agent` · `tool-agent` · `dev-agent` |
| 1.8 | Footer note | Every Start → create_run; each phase → upsert_step |

**Done when:** mmd renders; Draw.io page matches §3.8 ASCII in QA_AGENT_PLAN.

---

## Page 2 — Module Owns / Not

**Draw.io page name:** `Module Owns / Not`  
**Analogue:** agent-platform → Module Owns / Not  
**Mermaid source:** `sheets/modules.mmd`

| # | Task | Detail |
|---|------|--------|
| 2.1 | Write `sheets/modules.mmd` | Two-column owns / does-not-own flowchart |
| 2.2 | Add Draw.io page | Left **OWNS** · Right **DOES NOT OWN** |
| 2.3 | OWNS list | Temporal workflow · thin GitHub edge · registry · environments.yaml · release-policy · evidence_policy · learning gated · A2A adapters · WorkflowLedger · PDF templates · ChangeIntent · **await/request index only** |
| 2.4 | DOES NOT OWN list | fin-agent MetaEngine · ui-test Playwright · tool-agent plugins · **GitNexus sync/index Jobs (code-intelligence / per-repo)** · serve/analyze/FTS · dev-agent fixes · prompts in Python |

**Done when:** Matches support-agent boundary rules in QA_AGENT_PLAN §15–16.

---

## Page 3 — ReleaseReadiness E2E

**Draw.io page name:** `ReleaseReadiness E2E`  
**Analogue:** agent-platform → AlertIncident E2E  
**Mermaid source:** `sheets/e2e.mmd`  
**Spec:** QA_AGENT_PLAN §3.8, §5, §10.1, §14

| # | Task | Detail |
|---|------|--------|
| 3.1 | Write `sheets/e2e.mmd` | Full horizontal E2E (qa-route path) |
| 3.2 | Row 1 | `webhook` → … → **`await_gnx (Job)`** → `impact` → **`intent?`** → `gate` → `fin_prep` → `test_plan` → `execute` → `observe` → **`post_verify`** → **`analyze_llm`** → **`publish_pdf`** → `notify` |
| 3.3 | Row 2 | **`ReleaseEvidenceBundle`** → `readiness_gate` → `approve.release` (PDF preview) → `persist_episode` → `evaluate_learning` |
| 3.4 | Bottom boxes | `CI_fail → dev-route` · `reject.release` · `degraded → HITL banner` |
| 3.5 | Style | White boxes, `#D1D5DB` stroke, `#9CA3AF` arrows |

**Done when:** Side-by-side readable with AlertIncident E2E for parity review.

---

## Page 4 — GitNexus Sync + Fallback

**Draw.io page name:** `GitNexus Sync + Fallback`  
**Mermaid source:** `sheets/gnx-fallback.mmd`  
**Spec:** QA_AGENT_PLAN §9–§11

| # | Task | Detail |
|---|------|--------|
| 4.1 | Write `sheets/gnx-fallback.mmd` | Health → sync → index → FTS → L0–L3 decision tree |
| 4.2 | Swimlane **Intake** | `qa-route` · resolve repos · fetch `head_sha` |
| 4.3 | Swimlane **Sync** | tarball → `/data/repos` · `analyze --branch` · `repair-fts` · `group sync` |
| 4.4 | Swimlane **Fallback** | L0 full MCP · L1 GitHub compare · L2 hub capabilities · L3 smoke-defaults |
| 4.5 | Swimlane **Gate** | `intelligence_mode: degraded` · HITL banner · optional block |
| 4.6 | Footnote | index-serve.sh · group-am-portfolio.yaml |

**Done when:** §9–§11 fully represented on one page.

---

## Page 5 — Specialists (registry + adapters)

**Draw.io page name:** `Specialists`  
**Mermaid source:** `sheets/specialists.mmd`  
**Spec:** QA_AGENT_PLAN §7–§8, §12

| # | Task | Detail |
|---|------|--------|
| 5.1 | Write `sheets/specialists.mmd` | `registry/agents.yaml` → adapter → HTTP endpoint |
| 5.2 | Top | `config/environments.yaml` env resolution |
| 5.3 | Middle | `composition.build_runtime()` → A2A adapters |
| 5.4 | Bottom row | fin-agent `:8100` · ui-test `:8130` · tool-agent `:8141` · GitNexus MCP `:4747` · dev-agent TBD |
| 5.5 | Capabilities | `fin.data.prep` · `ui.test.run` · `observe.*` · **`document.*`** · `work-item.*` · `chat.message.send` |

**Done when:** Registry + specialist ports visible.

---

## Page 5b — LoadContext and specialist handoff

**Draw.io page name:** `LoadContext + Handoff`  
**Mermaid source:** `sheets/load-context.mmd`  
**Spec:** QA_AGENT_PLAN §12, §7.1, §8.1

| # | Task | Detail |
|---|------|--------|
| 5b.1 | Write `sheets/load-context.mmd` | webhook → resolve_load_profile → LoadContext → fin + ui payloads |
| 5b.2 | Center | **LoadContext** on WorkflowLedger |
| 5b.3 | Left | 5 config surfaces (#1–#5 from §12.1) |
| 5b.4 | Right top | fin-agent: `load.services[]`, `scenarios`, `impacted_ops` |
| 5b.5 | Right bottom | ui-test-agent: `TestRunRequest` (§7.1) |
| 5b.6 | Bottom | `load-rules.yaml` filter arrow |
| 5b.7 | Note | Secrets: `credential_refs` only |

**Done when:** Reader can trace webhook → env → LoadContext → both specialist JSON bodies.

---

## Page 5c — Verify + Publish (required)

**Draw.io page name:** `Verify + Publish`  
**Mermaid source:** `sheets/verify-publish.mmd`  
**Spec:** QA_AGENT_PLAN §14

| # | Task | Detail |
|---|------|--------|
| 5c.1 | Write `sheets/verify-publish.mmd` | H → comparison pack → H2 → LLM → PDF |
| 5c.2 | Center | **ReleaseEvidenceBundle.comparisons** |
| 5c.3 | Left | Grafana: latency · CPU/RAM · pods · users |
| 5c.4 | Right | LLM code+infra narrative + PDF sections |
| 5c.5 | Bottom | `feature_clean` + `infra_clean` from release-policy |

**Done when:** §14 pipeline readable without opening the plan markdown.

---

## Page 5d — Automation map (required)

**Draw.io page name:** `Automation map`  
**Mermaid source:** `sheets/automation-map.mmd`  
**Spec:** QA_AGENT_PLAN §23.2

| # | Task | Detail |
|---|------|--------|
| 5d.1 | Write `sheets/automation-map.mmd` | Three swimlanes: Deterministic · LLM (≤3) · HITL |
| 5d.2 | Draw.io page | Books footnote: CD · Accelerate · SRE · Explore It! · AI Engineering |
| 5d.3 | LLM boxes | `qa-change-intent` · optional `qa-test-spec-enrich` · `qa-release-analysis` |
| 5d.4 | Hard rules | Matrix SoT = GitNexus + load-rules; intent advisory; release = human |

**Done when:** Stakeholder can see what is automated vs LLM vs human in one page.

---

## Page 6 — Phases 0–4

**Draw.io page name:** `Phases 0-4`  
**Mermaid source:** `sheets/phases.mmd`  
**Spec:** QA_AGENT_PLAN §19

| # | Task | Detail |
|---|------|--------|
| 6.1 | Write `sheets/phases.mmd` | Timeline / checklist flowchart |
| 6.2 | Phase 0 | Webhook · CI classify · smoke ui-test · Cliq notify |
| 6.3 | Phase 1 | Request/await code-intelligence index Job · fin-agent · LoadContext · detect_changes or L1 |
| 6.4 | Phase 2 | ChangeIntent · Grafana · post-test verify · LLM analysis · PDF dossier |
| 6.5 | Phase 3 | Full API+UI+flow · matrix ranker §23.3 · ticket-only dev handoff · episodes |
| 6.6 | Phase 4 | HITL + PDF preview · learning · SAST-first security hook |

**Done when:** Matches QA_AGENT_PLAN §19.

---

## Page 7 — Final assembly

| # | Task | Detail |
|---|------|--------|
| 7.1 | Merge all pages into `qa-agent.drawio` | Single mxfile: **9** diagram pages + consistent styling |
| 7.2 | Verify in VS Code Draw.io Integration | All pages open without ID collisions |
| 7.3 | Update README.md | Mark pages complete; link drawio + schemas + examples |
| 7.4 | Update QA_AGENT_PLAN §3.8 | Remove “to create” wording; link live file |
| 7.5 | Optional | Add row to am-agents/docs/diagrams/README.md |

**Done when:** You can open `qa-agent.drawio` and navigate all **9** pages.

**Pages:** Four Layers · Module Owns / Not · ReleaseReadiness E2E · GitNexus Sync + Fallback · Specialists · LoadContext + Handoff · Verify + Publish · Automation map · Phases 0–4

---

## Batch D — Implementability artifacts (configs + schemas + ADRs)

**Not Draw.io** — raises plan implementability score. Spec: QA_AGENT_PLAN §20 defaults, §23.3–§23.5, §24.6.

| # | Task | Output |
|---|------|--------|
| D.1 | Write `config/examples/environments.yaml` | preprod + `inherits`, service_map, ui_targets |
| D.2 | Write `config/examples/load-rules.yaml` | path → fin services + ui profile (am-market, am-modern-ui sample) |
| D.3 | Write `config/examples/release-policy.yaml` | P0 thresholds, metric tolerance %, clean-feature rules, LLM gates |
| D.4 | Write `config/examples/smoke-defaults.yaml` | L3 fallback matrix |
| D.5 | Write `docs/schemas/*.schema.json` | LoadContext, ChangeIntent, ReleaseEvidenceBundle, WorkflowLedger QA |
| D.6 | Write `docs/decisions/README.md` + ADR-QA-001..004 stubs | Sync ownership, degraded release, ChangeIntent advisory, PDF store |
| D.7 | Add matrix-ranker note to README or short `docs/MATRIX_RANKER.md` | Pseudocode from §23.3 |

**Done when:** Engineer can scaffold Phase 0–1 without guessing merge rules or ledger fields.

---

## Suggested approval batches

| Batch | Scope | Effort |
|-------|-------|--------|
| **A** | Pages 0 + 1 + 2 | ~30 min — scaffold + layers + owns |
| **B** | Pages 3 + 4 + 5b + **5c** | ~55 min — E2E + GitNexus + LoadContext + verify/publish |
| **C** | Pages 5 + **5d** + 6 + 7 | ~40 min — specialists + automation map + phases + merge |
| **D** | Config examples + schemas + ADR stubs | ~45 min — implementability package |
| **All docs** | A + B + C + D | ~2.5–3 h |

Or say **“approved, start all”** for the full doc package (Draw.io + batch D) in one go.

---

## After doc package (code — separate approval)

From QA_AGENT_PLAN **§24**. Each row needs its own go-ahead.

| Phase | Work | Requires separate approval |
|-------|------|---------------------------|
| Code P0 | Scaffold `qa-agent/` from support-agent; webhook + smoke + Cliq | yes |
| Code P1 | `ReleaseReadinessWorkflow` + LoadContext + await index Job + fin-agent | yes |
| Code P2 | Observe + post_verify + ChangeIntent + LLM analysis + PDF | yes |
| Code P3 | Full matrix ranker · ticket-only dev handoff · episodes | yes |
| Code P4 | HITL UI · learning · SAST hook | yes |
| Infra | Helm, Temporal `qa-agent-v1`, GitHub App, Langfuse, Prometheus | **scaffolded** — see [BACKLOG.md](BACKLOG.md) for secrets/cluster |

---

## How to approve next

- `approved, start batch D` — configs/schemas/ADRs  
- `change: …` — revise Draw.io after review  
- Code scaffold still needs separate approval

**Draw.io is ready for review at [qa-agent.drawio](qa-agent.drawio).**
