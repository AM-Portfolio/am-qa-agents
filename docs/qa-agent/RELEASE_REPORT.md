# Release report runbook

End-to-end Asrax release evidence: UI suite + dossier pack + Google Sheet + 30m stability score + Cliq final summary.

Manual phase checklist (MCP + gate + Temporal): [MANUAL_VERIFICATION_CHECKLIST.md](./MANUAL_VERIFICATION_CHECKLIST.md)

## Ownership

| Concern | Repo |
|---------|------|
| Namespaces, risks, services, business SLIs | `am-infra/docs/releases/catalog/` |
| Sheet helpers | `am-infra/scripts/lib/asrax_release_sheet.py` |
| UI suite / score / Cliq / Temporal / npm | `am-qa-agents` |

## Preferred path: Cliq chat (single admin) → Temporal

Release does **not** start until one configured admin confirms in Zoho Cliq.

```text
POST /v2/releases/request  →  Cliq card in chat
        ↓
Admin clicks APPROVE (or replies: approve relreq-…)
        ↓
AsraxReleaseOpsWorkflow starts (UI + soak + Sheet/Drive + Cliq final)
```

Env (required for prod):

```powershell
$env:QA_AGENT_RELEASE_ADMIN="you@company.com"   # ONLY this person can approve
$env:QA_AGENT_PUBLIC_BASE_URL="https://qa-agent.example.com"  # links in Cliq card
$env:QA_AGENT_CLIQ_WEBHOOK_URL="https://cliq.zoho.in/..."     # outbound chat
$env:QA_AGENT_CLIQ_RELEASE_SECRET="..."   # HMAC on approve links (or reuse gateway token)
$env:QA_AGENT_GATEWAY_TOKEN="..."
# optional inbound bot:
# $env:QA_AGENT_CLIQ_INBOUND_TOKEN="..."
```

```powershell
# Gateway + Temporal worker must be running
npm run release:request:prod

# Admin opens Cliq → APPROVE link (or bot POSTs /webhooks/cliq/release)
# Then Temporal UI: AsraxReleaseOpsWorkflow
```

Inbound Cliq bot webhook: `POST /webhooks/cliq/release` with JSON  
`{"action":"approve","request_id":"relreq-...","actor":"admin@..."}`  
or chat text `"approve relreq-..."`. Actor must match `QA_AGENT_RELEASE_ADMIN`.

## Preferred path: Temporal (`AsraxReleaseOpsWorkflow`)

Use Temporal so each phase is visible in Temporal UI (Event History + Activity names) and ledger steps match 1:1.

```text
init → ui_suite → pack_t0 → soak → stability_score
  → publish_sheet → publish_drive → cliq_final → complete
```

Activity names (filter in Temporal UI): `activity_release_ops_*`

```powershell
cd A:\InfraCode\AM-Portfolio-grp\am-qa-agents

# Worker must be running (same queue as release-gate)
# python -m orchestrator.worker_main   # from qa-agent/release_gate with PYTHONPATH

# Lab dry-run (no UI / Sheet / Drive / Cliq)
npm run release:ops:inline

# Start real Temporal workflow (prod defaults; blocks only on start, not soak)
# Prefer Cliq approval above for real releases; this bypasses the admin gate:
npm run release:ops:prod
```

Then open Temporal UI → Workflows → `AsraxReleaseOpsWorkflow`. Failed activity + stack is on that step; `summary.json` under `artifacts/releases/{release_id}/` mirrors phase.

Inline (no worker): `npm run release:ops -- --inline ...` (same flags as script path below).

## Commands (script path, no Temporal)

```powershell
cd A:\InfraCode\AM-Portfolio-grp\am-qa-agents

$env:TEST_USER_EMAIL="..."
$env:TEST_USER_PASSWORD="..."
$env:TEST_PORTFOLIO_ID="..."
$env:ASRAX_RELEASE_SHEET_ID="1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc"
# optional: $env:QA_AGENT_CLIQ_RELEASE_WEBHOOK_URL="https://cliq.zoho.in/..."

# T0 — UI + pack + Sheet QA Evidence
npm run release:report:prod

# Final — soak (default 30m) + score + Drive + Cliq
npm run release:final:prod

# Lab / CI without waiting or live Grafana
npm run release:final -- --fixtures --soak-min 0 --skip-drive --skip-cliq --skip-sheet
```

One-shot scripts (blocks ~30m+): `npm run release:all:prod`

## Two Temporal workflows (do not confuse)

| What you open | Type | What it is |
|---------------|------|------------|
| `release-readiness-{repo}-{sha}-{env}` | `ReleaseReadinessWorkflow` | PR/CI gate: matrix → dossier PDF → **HITL approve** |
| `asrax-release-ops-{release_id}` | `AsraxReleaseOpsWorkflow` | **Asrax Release Pipeline**: Playwright UI + Sheet + soak/Grafana score + Drive + Cliq FINAL |

Example you opened ([history](https://temporal.asrax.in/namespaces/qa-agent/workflows/release-readiness-ssd2658-am-core-services-623b49995802-dev/019f99f9-24e4-72b6-9450-793c4bb57b6a/history)):
`ReleaseReadinessWorkflow` for `ssd2658/am-core-services` @ `623b49995802` / `dev`. It reached `activity_publish_pdf`, then waited 24h for HITL; after the timer it failed a workflow task. That run is **not** the Sheet/Grafana/soak FINAL pack.

For Asrax Release Pipeline filter: namespace `qa-agent`, `WorkflowType = "AsraxReleaseOpsWorkflow"`.

## Where each report lives

| Report | Where |
|--------|--------|
| Playwright / UI evidence | Local pack `artifacts/asrax-release-ops/{day}/{release_id}/ui/` (+ screenshots). MinIO under same release prefix |
| Google Sheet release template | [Asrax Release 01 sheet](https://docs.google.com/spreadsheets/d/1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc) (`ASRAX_RELEASE_SHEET_ID`) — append-only |
| Grafana after soak | Link in Cliq FINAL via `ASRAX_GRAFANA_SOAK_URL`; score in `final/stability-score.json` |
| One master PDF + pack | MinIO bucket `qa-agent` prefix `asrax-release-ops/{YYYY}/{YYYY-MM-DD}/{release_id}/` with dated object names (not am-infra Drive `Asrax/Releases`) |
| PR dossier PDF (readiness only) | Worker `{QA_AGENT_ARTIFACT_DIR}/{tracking_id}-release-dossier.pdf`. Open Temporal `activity_publish_pdf` for `pdf_docs_ref` |
| Cliq summary channel | Text card with Sheet + MinIO + Grafana + Temporal links |

## Artifact pack

Local: `artifacts/asrax-release-ops/{YYYY-MM-DD}/{release_id}/` (or `QA_AGENT_ARTIFACT_DIR/...`)

MinIO (canonical one instance): bucket `qa-agent` (override `MINIO_BUCKET` / `QA_AGENT_MINIO_BUCKET`), prefix `asrax-release-ops/{YYYY}/{YYYY-MM-DD}/{release_id}/`, dated object names including trigger + workflow stamps.

- `summary.json` — machine index (`phase`: INIT → UI_DONE → T0 → SCORED → FINAL)
- `master-release-report.html` (+ pdf when xhtml2pdf available)
- `ui/suite-*.json`
- `final/stability-score.json`, `cliq-message.md`, `final-analysis.html`
- MinIO also stores `…_pack-manifest.json` listing browser URLs

## Stability score

| Pillar | Weight |
|--------|--------|
| Technical | 40 |
| Alerts | 30 |
| Business | 30 |

Bands: STABLE ≥90 · ACCEPTABLE 75–89 · AT_RISK 50–74 · UNSTABLE &lt;50. Missing live metrics set pillar `unavailable` and cannot claim STABLE.

## Cliq final card

Posted at end of Asrax Release Pipeline / `release:final` (unless `--skip-cliq`). Includes band, pillar scores, Sheet URL, **MinIO** pack folder + master PDF link, UI summary, Grafana, Temporal filter link, action hint. Audit copy: `final/cliq-message.md`. Zoho incoming webhooks are **text + links only**; PDF/screenshots must be on MinIO with URLs in the card. Env: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`.

## Related

- [PROD_UI_FLOW_RUNBOOK.md](./PROD_UI_FLOW_RUNBOOK.md)
- [MANUAL_VERIFICATION_CHECKLIST.md](./MANUAL_VERIFICATION_CHECKLIST.md)
- [am-infra releases README](../../../am-infra/docs/releases/README.md)
