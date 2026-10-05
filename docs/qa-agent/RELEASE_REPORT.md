# Release report runbook

End-to-end Asrax release evidence: UI suite + dossier pack + Google Sheet + 30m stability score + Cliq final summary.

Manual phase checklist (MCP + gate + Temporal): [MANUAL_VERIFICATION_CHECKLIST.md](./MANUAL_VERIFICATION_CHECKLIST.md)

## How to generate a report

From `am-qa-agents` (`f:\am-repos\am-repos\am-qa-agents`). Do **not** start a new plan for the daily Drive pack — use the command below.

| Kind | Command | What you get |
|------|---------|----------------|
| **Daily Drive pack** (no UI, no soak) | `npm run release:ops:drive` | Local pack + Google Drive folder. Does **not** claim STABLE. **No Cliq.** Optional GitHub open `feature/*` PR list in the pack. |
| **Full release evidence** | Cliq approve → Temporal, or `npm run release:ops:prod` / `npm run release:all:prod` | Playwright on https://am.asrax.in + 30m soak + Sheet + Drive + Cliq FINAL |
| **Per-PR / feature-branch gate** | GitHub webhook → `ReleaseReadinessWorkflow` | SHA compare + dossier PDF. **Not** the Drive pack. |

Daily Drive pack (repeatable):

```powershell
cd f:\am-repos\am-repos\am-qa-agents
npm run release:ops:drive -- --release-name "YYYY-MM-DD drive pack"
```

**n8n (one trigger → entire AsraxReleaseOps):** workflow JSON lives in **`am-n8n-workflows`** (sibling repo, not always in the Cursor workspace). Path: [`packages/support/workflows/qa-release-ops.json`](../../../am-n8n-workflows/packages/support/workflows/qa-release-ops.json).

- Add folder `f:\am-repos\am-repos\am-n8n-workflows` to the workspace (File → Add Folder to Workspace).
- n8n UI: [preprod](https://n8n-preprod.asrax.in) → open **qa-release-ops** → Execute, or `POST` webhook `/webhook/qa-release-ops`.
- Calls `POST /qa/v2/releases/ops/start` (Bearer `QA_AGENT_GATEWAY_TOKEN`). Defaults = Drive pack. Full UI+soak: body `{ "skip_ui": false, "soak_min": 30 }`.
- Import: `.\scripts\import.ps1 -Target preprod -Pack support` from `am-n8n-workflows`.

**Subscription-only pack (GitHub, not n8n):** on push to `am-platform` `main` under `am-subscription/**`, workflow [`.github/workflows/subscription-qa-on-main.yml`](../../../am-platform/.github/workflows/subscription-qa-on-main.yml) calls ops/start with `suite=subscription_module`, `api_pack=subscription`, `env=preprod`, `requested_by=github-merge`. Manual re-run: Actions → **Subscription QA on main** → Run workflow. Mapping: [`SUBSCRIPTION_MODULE_CATALOG.md`](../../qa-agent/ui_evidence/docs/SUBSCRIPTION_MODULE_CATALOG.md). Specs portal Runs use the returned `tracking_id`.

Equivalent flags: `--inline --skip-ui --skip-soak --skip-cliq --soak-min 0 --env prod`.

**Prereqs**

- `GOOGLE_APPLICATION_CREDENTIALS` (or `GOOGLE_DRIVE_CREDENTIALS`) → service-account JSON with Drive + Sheets scope. amctl: `am creds` / `~/.asrax/secrets/`.
- Helper: [`am-infra/scripts/lib/asrax_release_sheet.py`](../../../am-infra/scripts/lib/asrax_release_sheet.py)
- Sheet id: `ASRAX_RELEASE_SHEET_ID` (default [Asrax Release 01](https://docs.google.com/spreadsheets/d/1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc))

**Where files go**

| Place | Path |
|-------|------|
| Local pack | `artifacts/asrax-release-ops/{YYYY-MM-DD}/{release_id}/` |
| Google Drive | `QA-Agent / Asrax-Release-Ops / {year} / {YYYY-MM-DD} / {release_id}` (not `Asrax/Releases`) |
| Google Sheet | append-only QA Evidence + Stability tabs |
| Temporal | namespace `qa-agent`, `WorkflowType = "AsraxReleaseOpsWorkflow"` (daily pack uses `--inline`, so no Temporal run) |

Do not pass `--fixtures` on a real day's pack (that fakes STABLE). Lab dry-run: `npm run release:ops:inline`.

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
cd f:\am-repos\am-repos\am-qa-agents

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
cd f:\am-repos\am-repos\am-qa-agents

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
| Google Drive pack (ops) | `QA-Agent/Asrax-Release-Ops/{year}/{YYYY-MM-DD}/{release_id}` — master HTML/PDF + `summary.json` |
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
- `github-feature-prs.json` — optional open AM-Portfolio `feature/*` PRs (daily Drive pack)
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
