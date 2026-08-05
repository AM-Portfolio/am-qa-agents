# Manual verification checklist — Zoho / Temporal MCP + release gate

Work **one phase at a time**. After you confirm the Expected result, mark that phase `[x]` and note date/initials. Do not skip ahead if a prior phase fails.

**Owner:** you (manual review)  
**Repos:** `amctl` (MCP) + `am-qa-agents` (release)  
**Secrets:** never paste webhook URLs, tokens, or passwords into this file or chat

---

## Progress board

| Phase | Name | Status |
|-------|------|--------|
| 0 | Preflight — creds + MCP green | [x] 2026-08-06 |
| 1 | Zoho Cliq MCP — read status | [x] primary/release configured; writes_enabled true |
| 2 | Zoho Cliq MCP — test post | [x] user saw `AM MCP verify` / `Phase 2 smoke [summary]` in Cliq (summary webhook) |
| 3 | Temporal MCP — Asrax Release Pipeline | [~] MCP OK; **confirm via `AsraxReleaseOpsWorkflow` only** (not ReleaseReadiness). Inline dry COMPLETED `asrax-r01-20260805-8ee1a8e5` — check Cliq **Asrax Release Pipeline** / summary channel |
| 4 | Official Zoho MCP (optional) | [ ] N/A if no `ZOHO_MCP_URL` |
| 5 | Automated unit tests | [ ] |
| 6 | Inline release ops (all phases dry) | [x] COMPLETED STABLE — `asrax-r01-20260805-8ee1a8e5` |
| 7 | Cliq approval gate (local gateway) | [ ] |
| 8 | Temporal UI — live workflow phases | [ ] |
| 9 | Prod request path (optional soak) | [ ] |

### Phase 2 verification note (why you saw nothing from MCP)

- Cursor **zoho-cliq** MCP had started **before** Vault sync / `AM_ZOHO_CLIQ_MCP_WRITE=1`, so tools reported all `false` and would not post.
- Direct posts with the same Vault webhooks returned **HTTP 204** (Zoho accepted). Look in **India DC** Cliq: https://cliq.zoho.in — channels tied to **opslab / lab / summary** webhooks from `am-agents` (not necessarily a personal DM).
- Fix applied: bridge reloads creds on every tool call; `AM_ZOHO_CLIQ_MCP_WRITE=1` in `credentials.env` + `mcp.json` env. **Reload MCP server `zoho-cliq` in Cursor**, then re-check Phase 1–2.

---

## Phase 0 — Preflight

**Goal:** Confirm Cursor MCP servers are up and credentials keys exist (values stay private).

### Steps
1. Cursor → MCP / Tools: confirm **zoho-cliq** and **temporal** show connected (green).
2. In PowerShell (no secret print):

```powershell
Select-String -Path "$env:USERPROFILE\.am\credentials.env" -Pattern '^(ZOHO_CLIQ_|QA_AGENT_CLIQ_|TEMPORAL_|ZOHO_MCP_|AM_ZOHO_CLIQ|AM_TEMPORAL)' |
  ForEach-Object { ($_.Line -split '=',2)[0] + '=' + $(if (($_.Line -split '=',2)[1]) {'set'} else {'empty'}) }
```

3. Expect at least: `ZOHO_CLIQ_WEBHOOK_URL=set`, `TEMPORAL_ADDRESS=set`, `TEMPORAL_NAMESPACE=set` (should be `qa-agent`).
4. For write tests later, ensure in credentials (or session):
   - `AM_ZOHO_CLIQ_MCP_WRITE=1`
   - keep `AM_TEMPORAL_MCP_WRITE=0` until Phase 8 write tools are needed

### Expected
- MCP UI: zoho-cliq + temporal healthy
- Key presence lines show `set` (not empty) for Cliq + Temporal

### Pass when
You see green MCP + key presence OK.

**Verified:** [ ] ____ / ____  
**Notes:** ________________________________

---

## Phase 1 — Zoho Cliq MCP (read-only)

**Goal:** Prove bridge loads creds without posting.

### Steps (ask Cursor agent or use MCP tool panel)
1. Call tool **`cliq_webhook_status`** on server **zoho-cliq**.

### Expected (JSON-ish)
- `primary_configured`: true
- `release_configured`: true
- `writes_enabled`: true or false (note which; Phase 2 needs true)
- no error / no stack trace

### Pass when
Status returns configured flags correctly.

**Verified:** [ ] ____ / ____  
**Notes:** ________________________________

---

## Phase 2 — Zoho Cliq MCP (write smoke)

**Goal:** One real message lands in the Cliq channel (lab/summary webhook).

### Steps
1. Confirm `AM_ZOHO_CLIQ_MCP_WRITE=1` (reload MCP if you just set it).
2. Call **`cliq_post_card`**:
   - `title`: `AM MCP verify`
   - `body`: `Phase 2 smoke — ignore`
   - `use_release_webhook`: `false` first (primary), then optionally `true` for release channel
3. Open Zoho Cliq channel for that webhook.

### Expected
- Tool returns `"ok": true` (or HTTP 200-class)
- Message visible in Cliq within ~30s

### Pass when
You see the card in Cliq.

**Verified:** [ ] ____ / ____  
**Notes:** ________________________________

---

## Phase 3 — Temporal MCP (Asrax Release Pipeline)

**Goal:** Confirm connectivity and that verification uses **`AsraxReleaseOpsWorkflow`** (Asrax Release Pipeline), not `ReleaseReadinessWorkflow`.

### Steps
1. Temporal MCP: `get_cluster_info`, `describe_namespace` (`qa-agent`), list with query:
   `WorkflowType = 'AsraxReleaseOpsWorkflow'`
2. Browser: https://temporal.asrax.in → namespace **qa-agent** → filter **AsraxReleaseOpsWorkflow**.
3. Cliq channel for pipeline cards: same webhook as Phase 2 summary / release (**Asrax Release Pipeline**). Look for titles starting with `Asrax Release Pipeline —`.
4. Until a live Temporal worker run exists, accept **inline** dry-run `summary.json` with `"workflow": "AsraxReleaseOpsWorkflow"` as phase evidence (Phase 6).

### Expected
- Cluster reachable; namespace `qa-agent` registered
- Cliq shows pipeline verify cards on the summary/release channel
- Live UI rows appear only after `npm run release:ops` / approve-gate starts a worker run (0 runs is OK before Phase 8)

### Pass when
You confirm Cliq **Asrax Release Pipeline** card(s) and understand Temporal filter is `AsraxReleaseOpsWorkflow`.

**Verified:** [ ] ____ / ____  
**Notes:** release_id example `asrax-r01-20260805-8ee1a8e5` (inline COMPLETED / STABLE)

---

## Phase 4 — Official Zoho MCP (optional)

**Goal:** Only if you created a server at https://mcp.zoho.com and set `ZOHO_MCP_URL`.

### Steps
1. Confirm `ZOHO_MCP_URL=set` in credentials (Phase 0 pattern). If empty → mark **N/A** and skip.
2. Cursor MCP **zoho** green.
3. Call one **read** Cliq/Zoho tool from that server (not webhook bridge).

### Expected
- Tool list loads; one read succeeds

### Pass when
Official Zoho MCP works **or** marked N/A.

**Verified:** [ ] ____ / ____ / N/A  
**Notes:** ________________________________

---

## Phase 5 — Automated unit tests

**Goal:** Regression baseline before live gate.

### Steps

```powershell
cd A:\InfraCode\AM-Portfolio-grp\amctl
python -m pytest -q tests/test_mcp_bridges.py tests/test_ai_catalog.py

cd A:\InfraCode\AM-Portfolio-grp\am-qa-agents
npm run agent:test
```

### Expected
- amctl MCP tests pass
- qa-agent tests pass (includes `test_asrax_release_ops` + `test_cliq_release_gate`)

### Pass when
Both command sets exit 0.

**Verified:** [ ] ____ / ____  
**Notes:** ________________________________

---

## Phase 6 — Inline release ops (dry phases)

**Goal:** Walk every release phase without Temporal worker / live soak.

Phases exercised:

```text
init → ui_suite → pack_t0 → soak → stability_score
  → publish_sheet → publish_drive → cliq_final → complete
```

(With flags: skip UI/soak/sheet/drive/cliq + fixtures.)

### Steps

```powershell
cd A:\InfraCode\AM-Portfolio-grp\am-qa-agents
npm run release:ops:inline
```

4. Open newest folder under `artifacts/releases/` and read `summary.json`.

### Expected
- Console: workflow **COMPLETED** (or equivalent success)
- `summary.json` shows phase order completed / STABLE-style score when fixtures used
- Artifact pack path printed

### Pass when
Inline run completes and `summary.json` looks sane.

**Verified:** [ ] ____ / ____  
**Release id / pack path:** ________________________________

---

## Phase 7 — Cliq approval gate (local)

**Goal:** Request → admin approve → workflow start (inline or Temporal). Stop after approve so you can review gate behavior.

### Pre-req env (session; do not commit)

```powershell
$env:QA_AGENT_RELEASE_ADMIN="YOUR_EMAIL@..."   # only this actor may approve
$env:QA_AGENT_PUBLIC_BASE_URL="http://127.0.0.1:PORT"  # gateway public base
$env:QA_AGENT_CLIQ_WEBHOOK_URL="..."           # from Vault / credentials
$env:QA_AGENT_CLIQ_RELEASE_SECRET="local-test-secret"
# gateway token if your gateway requires it
```

### Steps
1. Start qa-agent gateway (your usual `npm run backend:start` / gateway entry).
2. Request:

```powershell
cd A:\InfraCode\AM-Portfolio-grp\am-qa-agents
npm run release:request -- --env lab --suite lab_smoke --url http://127.0.0.1 --soak-min 0 --gateway http://127.0.0.1:PORT
```

3. Confirm Cliq shows **RELEASE APPROVAL** card with APPROVE / REJECT links.
4. As `QA_AGENT_RELEASE_ADMIN`, open APPROVE (or POST inbound webhook with matching actor).
5. Confirm request status becomes approved and workflow start attempted.

### Expected
- Pending request created (`relreq-...`)
- Card in Cliq
- Approve only works for admin email
- After approve: Temporal start **or** inline fallback logged

### Pass when
You personally approved once and saw start side-effect.

**Verified:** [ ] ____ / ____  
**request_id:** ________________________________

---

## Phase 8 — Temporal UI live phases

**Goal:** Same phase list as Phase 6, but visible in Temporal UI under `AsraxReleaseOpsWorkflow`.

### Pre-req
- Temporal worker running for release-gate task queue / namespace `qa-agent`
- Prefer start via Phase 7 approve, or:

```powershell
npm run release:ops:prod
```

(bypass gate — lab only)

### Steps
1. Open https://temporal.asrax.in → namespace **qa-agent** → Workflows → `AsraxReleaseOpsWorkflow`.
2. For the run, walk Event History / Activities:
   - `activity_release_ops_init`
   - `activity_release_ops_ui_suite`
   - `activity_release_ops_pack_t0`
   - soak / `activity_release_ops_stability_score`
   - `activity_release_ops_publish_sheet`
   - `activity_release_ops_publish_drive`
   - `activity_release_ops_cliq_final`
   - complete
3. Optionally confirm same phases via Temporal MCP read tools.
4. Mirror check: `artifacts/releases/{release_id}/summary.json`.

### Expected
- Each activity Completes (or fails with clear reason you accept)
- Cliq final card if not skipped
- Pack on disk matches Temporal status

### Pass when
You reviewed the full activity chain for one run.

**Verified:** [ ] ____ / ____  
**workflow_id / run_id:** ________________________________

---

## Phase 9 — Prod request path (optional / long)

**Goal:** Real prod UI + soak. Only after Phases 0–8 pass.

### Steps
1. Set prod test user env (`TEST_USER_*`, sheet id, Cliq, release admin, public base URL).
2. Gateway + Temporal worker up.
3. `npm run release:request:prod`
4. Admin approve in Cliq.
5. Watch Temporal through soak (default 30m).
6. Confirm Sheet / Drive / Cliq final.

### Expected
- Full COMPLETED run with real evidence (not fixtures)

### Pass when
Prod evidence reviewed once.

**Verified:** [ ] ____ / ____  
**Notes:** ________________________________

---

## Sign-off

| Role | Name | Date | Result |
|------|------|------|--------|
| Verifier | | | PASS / FAIL / PARTIAL |
| Blockers | | | |

**DONE when:** Phases 0–3, 5–7 are `[x]` (4 optional; 8–9 as needed for prod claim).
