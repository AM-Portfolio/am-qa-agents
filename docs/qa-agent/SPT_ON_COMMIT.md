# Commit → SPT (Temporal / qa-agent worker)

**SPT does not run on a GitHub Actions runner.** GitHub (or a webhook) only
**starts** `CommitSptWorkflow`. The **qa-agent Temporal worker pod** executes
k6, then emails the committer and posts Zoho Cliq.

The short hex on Runs (e.g. `67680b6c`) is the **SPT run UUID prefix**, not a
GitHub Actions run id and not a pod id. Overview shows real CI provenance when
present (Trigger, Branch, Committer, **GitHub run** link).

## Triggers

| Trigger | Path |
|---------|------|
| **After Contabo deploy** | `enable_commit_spt: true` on Contabo publish → thin glue jobs → [`spt-after-deploy.yml`](../../.github/workflows/spt-after-deploy.yml) |
| **Preferred without deploy** | GitHub webhook → `POST /qa/webhooks/github` (push to `am-market` touching `am-market-data/**`) |
| Manual / API | `POST /qa/v2/workflows/commit-spt` with gateway bearer |
| Optional push GHA | `qa-agent-spt-notify.yml` only if `SPT_USE_GHA_START=true` (default off) |

### Post-deploy (separate workflow file)

SPT start logic lives only in **am-qa-agents** [`spt-after-deploy.yml`](../../.github/workflows/spt-after-deploy.yml).
**am-pipelines** Contabo publish has thin `uses:` glue only (delete those jobs to migrate away).

| Contabo outcome | SPT |
|-----------------|-----|
| Contabo Argo → **dev** success | Start SPT against `https://am-dev.asrax.in/qa` |
| Contabo Argo → **preprod** success | Start SPT against `https://am-preprod.asrax.in/qa` |
| Contabo Argo → **prod** success | Start SPT against `https://am.asrax.in/qa` |
| Contabo Argo → **dr** | No SPT (no target in `spt.yaml`) |
| Contabo Argo → env **failed** | SPT job for that env is **Skipped** (other envs still run) |
| Auto sync → preprod **success** | SPT for **preprod** (does not wait on Approve) |
| Auto sync → preprod **failed** | `spt-after-auto-sync` **Skipped** |

Wire a service: pass `enable_commit_spt: true` into
`central-build-publish-contabo.yml` (see `am-market` `market-data.yml`).
Requires secret `QA_AGENT_GATEWAY_TOKEN` on the caller (inherited into Contabo).

## Env → QA domain

From [`qa-agent/spt.yaml`](../../qa-agent/spt.yaml):

| Env | QA base |
|-----|---------|
| `dev` | `https://am-dev.asrax.in/qa` |
| `preprod` | `https://am-preprod.asrax.in/qa` |
| `prod` | `https://am.asrax.in/qa` |

## Branch matrix

| Git ref | Dataset | Intensity | Fail job semantics |
|---------|---------|-----------|--------------------|
| `feature/**`, `fix/**`, … | `working` | `debug` 1×1 (`ci-smoke`) | Report-only |
| `develop`, `dev` | `working` | `debug` 1×1 | Fail workflow if unexpected > 0 |
| `main` | `full` | `ci-load` ramp + 100 iters | Fail if unexpected > 0 |

## API body

```json
{
  "service": "am-market-data",
  "repo": "AM-Portfolio/am-market",
  "branch": "feature/spt-smoke",
  "head_sha": "abc123…",
  "environment": "dev",
  "committer_email": "you@example.com",
  "committer_name": "You",
  "use_temporal": true,
  "trigger_source": "github_actions",
  "github_run_id": "38078000844",
  "github_run_url": "https://github.com/AM-Portfolio/am-market/actions/runs/38078000844",
  "github_workflow": "Market Data Publish",
  "github_event_name": "push",
  "commit_message": "feat: …"
}
```

Response includes `tracking_id` + `workflow_id`. Poll ledger `GET /v2/runs/{tracking_id}` or Temporal UI.

Provenance fields are stored on `payloads_used.run_params` and shown on Overview.

## Secrets / env (qa-agent dig)

| Name | Purpose |
|------|---------|
| `QA_AGENT_GATEWAY_TOKEN` | Auth for `/v2/workflows/commit-spt` (also GHA secret on service repos) |
| `GITHUB_WEBHOOK_SECRET` | HMAC for `/webhooks/github` |
| `ZOHO_CLIQ_SPT_WEBHOOK_URL` (or `QA_AGENT_CLIQ_WEBHOOK_URL`) | Team Cliq |
| `SPT_SMTP_*` | Email committer (optional) |
| `SPT_BOOTSTRAP_KEYS` | Include `ci:…` if ACL required |

## Webhook setup (once)

On `AM-Portfolio/am-market` → Settings → Webhooks:

- Payload URL: `https://am-dev.asrax.in/qa/webhooks/github`
- Content type: `application/json`
- Secret: same as dig `GITHUB_WEBHOOK_SECRET`
- Events: **Just the push event**

Keep `SPT_USE_GHA_START` unset or not `true` so the optional push starter stays off.
