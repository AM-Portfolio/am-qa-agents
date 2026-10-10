# Commit → SPT (Temporal / qa-agent worker)

**SPT does not run on a GitHub Actions runner.** GitHub (or a webhook) only
**starts** `CommitSptWorkflow`. The **qa-agent Temporal worker pod** executes
k6, then emails the committer and posts Zoho Cliq.

## Triggers

| Trigger | Path |
|---------|------|
| **Preferred** | GitHub webhook → `POST /qa/webhooks/github` (push to `am-market` touching `am-market-data/**`) |
| Manual / API | `POST /qa/v2/workflows/commit-spt` with gateway bearer |
| Optional GHA | `qa-agent-spt-notify.yml` fire-and-forget POST only (set `SPT_USE_GHA_START=false` when webhook is live) |

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
  "use_temporal": true
}
```

Response includes `tracking_id` + `workflow_id`. Poll ledger `GET /v2/runs/{tracking_id}` or Temporal UI.

## Secrets / env (qa-agent dig)

| Name | Purpose |
|------|---------|
| `QA_AGENT_GATEWAY_TOKEN` | Auth for `/v2/workflows/commit-spt` |
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

Then set repo variable `SPT_USE_GHA_START=false` so the optional GHA starter stays off.
