# Upcoming work & test — qa-agent pilot

Last updated: **2026-07-22** (end of day handoff)

**Ownership / do–don’t (many agents):** [AGENTS_OWNERSHIP_AND_DONT.md](AGENTS_OWNERSHIP_AND_DONT.md) — qa = conductor; don’t duplicate specialists or build a second orchestrator.

**Goal for next session:** one Temporal pilot where every *required* step is `live` (or honest `skipped` only where product chooses), dossier is fully populated, and ledger shows **no unexpected fails**.

**Latest good run:** `qa-f2988c249a93`  
Workflow: `release-readiness-ssd2658-am-core-services-pilotc9a9ea3-dev`  
Temporal: https://temporal.asrax.in/namespaces/qa-agent/workflows/release-readiness-ssd2658-am-core-services-pilotc9a9ea3-dev  
Artifacts: `artifacts/pdf/qa-f2988c249a93-release-dossier.{html,pdf}`  
*(Ignore `qa-pdfprobe-*` — empty PDF-engine smoke only.)*

---

## 1. Done this session (keep)

### Architecture / Temporal
- Isolated Temporal: namespace **`qa-agent`**, queue **`qa-agent-release-v1`**
- CI → HTTP gateway → Temporal (not Temporal client from CI)
- Pilot target: **am-core-services / am-analysis**, env **dev**
- Activity modules renamed to domain names:
  - `intake.py` — classify, LoadContext, index, fin prep, notify
  - `testing.py` — ChangeIntent, matrix, execute, handoff, episodes
  - `evidence.py` — observe, verify, analyze, PDF
  - `governance.py` — SAST, HITL, GitHub checks, learning

### MCP / fallbacks (honest modes)
- Shared `adapters/mcp_fallback.py`:
  - tool-agent **`/api/v1/tools/execute`** (not dead `/v1/a2a/execute`)
  - GitNexus MCP with correct `Accept` header
- Modes: `live` | `fallback_mcp` | `fallback_gnx` | `fallback_template` | `skipped`
- UI skip no longer fake-`COMPLETED`

### am-analysis API path (real load)
- `adapters/api_load.py` — live HTTP against LoadContext `base_url`
- `service=am-analysis` → **Analysis Service** only + `health_smoke` / `contract_smoke`
- **fin_data_prep** = live readiness probe (fin-agent has no `/meta/discover` on deploy)
- **execute_matrix API** = real load (default 5 VUs × 8) on  
  `https://am-dev.asrax.in/analysis/actuator/health/readiness`
- P0 API gate uses real pass/fail (not prep stub)

### Dossier / PDF
- Always write HTML; PDF via **xhtml2pdf** (WeasyPrint needs GTK on Windows)
- Readable API results table + endpoint rows from API load when Grafana empty
- Analysis narrative mentions API vs UI separately

### Config / ops
- `config/environments.yaml` — real am-platform Identity/Users/Auth paths
- `config/load-rules.yaml` — analysis scenarios + am-analysis narrowing
- Local: gateway `:8150`, Temporal PF `:7233`, tool-agent `:8141`, fin `:8100`
- Cliq notify live; trigger policy allow am-analysis / deny others

### Tests added
- `tests/test_mcp_fallback.py`
- `tests/test_api_load.py` (+ load-profile am-analysis assert)
- Full suite was green (~37+) after renames

---

## 2. Left out (blockers → “complete without fails”)

| # | Gap | Blocker | Unblock (owner) | Done when |
|---|-----|---------|-----------------|-----------|
| P0 | **UI tests** | Vault paths missing: `apps/data/dev/services/am-ui-test-agent`, `apps/data/dev/infra/qdrant`; `QA_AGENT_SKIP_UI_TEST=true` | Vault secrets + pod Ready; set skip **false** | ledger `ui_status` live/`COMPLETED`, not SKIPPED |
| P0 | **Grafana observe** | datasource UID / empty series → `unavailable: live_grafana_series` | Fix Grafana MCP datasource; confirm PromQL in catalog | dossier §5 CPU/RAM + §6 users `source≠template` |
| P1 | **LLM narratives** | Together **402** credits / Langfuse prompts | Credits or alternate model on LiteLLM; wire `qa-change-intent` / `qa-release-analysis` | `mode=litellm` (or named model), not `fallback_template` |
| P1 | **contract_smoke** | OpenAPI **401** counted as “exists” | Service account / allowlist for `v3/api-docs`, or fin MetaEngine with auth | contract row PASS with **200** + schema smoke |
| P1 | **GrowthBook** | snapshot **401** | Correct API/SDK key for env | security step `growthbook.ok=true` |
| P2 | **GitHub check-run** | `GITHUB_TOKEN` empty + skip true | PAT with checks:write; `QA_AGENT_SKIP_GITHUB_CHECKS=false` | check appears on SHA |
| P2 | **SAST** | CI Semgrep/CodeQL not wired | Pass CI conclusion / artifact into activity | `mode` not only heuristic template |
| P2 | **SPT k6** | plugin disabled / stub adapter | Enable SPT + real k6 runner; then prefer over direct HTTP | `spt.execute` live; keep direct load as backup |
| P3 | **fin-agent meta** | Deploy is chat-only (`/v1/ai/*`) | Deploy `am_fin_api_testing` routes or keep URL probe | optional; probe already OK |
| P3 | **Document store** | MinIO/document plugin + skip | Enable document.put when ready | `pdf_docs_ref` remote URL |
| P3 | **Learning promote** | heuristic stub | Offline job + HITL promote | not required for release gate |

---

## 3. Definition of done — “complete result, no fails”

A pilot is **green** when **all** of the following hold:

1. Temporal workflow **Completed**, status `release_approved` (or intentional `release_rejected`)
2. Ledger modes:
   - `await_index` → `live`
   - `fin_data_prep` → `live`
   - `execute_matrix` API → `PASSED` / `live`, `api_failed=[]`, `p0_failed=[]`
   - UI → **not** SKIPPED *(or product explicitly accepts skip)*
   - `collect_comparisons` → `observe` or live series (not empty Grafana)
   - `analyze_release` → LLM live **or** accepted template with honest `mode`
3. Dossier (`qa-*-release-dossier.pdf`) shows:
   - API table with PASS + real p50/p95
   - Infra table **not** “Grafana not live”
   - Users `source` not `template`
   - Verification releasable + empty blockers
4. `npm run pilot:local` exit 0; deny path still skips non-allowed services
5. No step status `FAILED` unless it is a deliberate gate hold

**Acceptable intentional skips (document in ledger):** document store, DAST off, learning stub — until P2/P3 above.

---

## 4. Priority test plan (next session)

### P0 — unblock & re-pilot (do first)

| # | Test | How | Pass criteria |
|---|------|-----|---------------|
| T1 | Unit smoke | `python -m pytest tests/ -q` | all green |
| T2 | Analysis health | `GET https://am-dev.asrax.in/analysis/actuator/health/readiness` | 200 |
| T3 | API load unit/live | `pytest tests/test_api_load.py -q` + optional live probe | PASSED Analysis Service |
| T4 | Temporal PF | `kubectl -n temporal port-forward svc/temporal-frontend 7233:7233` | TCP 7233 |
| T5 | Gateway + worker | `npm run gateway` / `npm run worker` | listen 8150 + queue |
| T6 | Full pilot | `npm run pilot:local` | `release_approved`; open **new** dossier (not pdfprobe) |
| T7 | Ledger check | `GET /v2/runs/{tracking_id}` | API live; note remaining skips |

### P1 — make dossier “full” (after Vault / Grafana / LLM)

| # | Test | How | Pass criteria |
|---|------|-----|---------------|
| T8 | Vault ui-test | Write secrets; restart ui-test pod; `QA_AGENT_SKIP_UI_TEST=false` | UI not SKIPPED |
| T9 | Grafana observe | Fix datasource UID; re-pilot | §5/§6 live data |
| T10 | LiteLLM | Fix credits/model; enable LLM | change_intent / analyze not template-only |
| T11 | Contract auth | Auth for api-docs or fin batch | contract PASS @ 200 |
| T12 | GrowthBook | Fix key → re-pilot | `growthbook.ok` |

### P2 — CI / GitHub / SPT parity

| # | Test | How | Pass criteria |
|---|------|-----|---------------|
| T13 | GitHub check | Set `GITHUB_TOKEN`, unset skip | check-run on commit |
| T14 | CI notify | Push am-analysis with secrets | workflow hits gateway |
| T15 | SPT enable | `TOOL_AGENT_CAPABILITY_PLUGINS=spt` + k6 | optional; direct load still OK |

### P3 — polish

| # | Test | How | Pass criteria |
|---|------|-----|---------------|
| T16 | Commit + PR | commit qa-agent changes (not yet) | reviewable PR |
| T17 | In-cluster deploy | helm values / image | worker in cluster on same queue |
| T18 | Delete probe artifacts | remove `qa-pdfprobe-*` when file unlocked | no confusion in folder |

---

## 5. Local re-run checklist (copy/paste)

```powershell
cd f:\am-repos\am-repos\qa-agent
$env:KUBECONFIG="f:\am-repos\am-repos\VPS\VPS\kubeconfig.vps"

# PF (if needed)
kubectl -n temporal port-forward svc/temporal-frontend 7233:7233
# optional: fin 8100, tools 8141, litellm 4000, ui-test 8130

npm run gateway    # :8150
npm run worker     # qa-agent-release-v1

python -m pytest tests/ -q
npm run pilot:local

# Open newest real dossier (not pdfprobe):
# artifacts/pdf/qa-*-release-dossier.pdf
# Temporal UI: https://temporal.asrax.in/namespaces/qa-agent/workflows/<workflow_id>
```

**Env knobs (`.env`):**

| Var | Today | For green UI/API/observe |
|-----|-------|---------------------------|
| `QA_AGENT_SKIP_UI_TEST` | `true` | `false` after Vault |
| `QA_AGENT_SKIP_GITHUB_CHECKS` | `true` | `false` + token |
| `QA_AGENT_SKIP_OBSERVE` | `false` | keep false; fix Grafana |
| `QA_AGENT_API_LOAD_VUS` / `ITERATIONS` | `5` / `8` | tune load |
| `QA_AGENT_SKIP_PDF` | `false` | keep |
| `GITHUB_TOKEN` | empty | set for checks |

---

## 6. Fallback modes (ledger)

| `mode` | Meaning | Replace later with |
|--------|---------|-------------------|
| `live` / `observe` / `litellm` | Real path worked | — |
| `fallback_mcp` | tool-agent `/api/v1/tools/execute` | Specialist API |
| `fallback_gnx` | GitNexus `/api/mcp` | Index Job + impact |
| `fallback_template` | Local stub | Real SAST/LLM/observe |
| `skipped` | Explicit env skip | Unset `QA_AGENT_SKIP_*` |

---

## 7. Suggested next-day order (1–2 hours)

1. **T1–T7** — confirm nothing regressed overnight (15–20 min)  
2. **Vault ui-test (P0)** — longest pole; then T8  
3. **Grafana datasource (P0)** — T9; dossier infra/users fill  
4. **LiteLLM credits (P1)** — T10  
5. Re-pilot → compare ledger to §3 Definition of done  
6. Only then GitHub / SPT / commit (P2–P3)

If blocked on Vault/Grafana, still ship API-load path as the release-gate proof for **am-analysis**, and keep UI/observe as tracked exceptions in the dossier appendix.
