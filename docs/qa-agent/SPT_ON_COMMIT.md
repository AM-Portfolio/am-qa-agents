# Commit → SPT (am-market-data pilot)

Push to `am-market` under `am-market-data/**` triggers [qa-agent-spt-notify.yml](../../../../am-market/.github/workflows/qa-agent-spt-notify.yml), which calls the reusable workflow [spt-on-commit.yml](../../.github/workflows/spt-on-commit.yml).

## Branch matrix

| Git ref | Dataset | Intensity | Shape | Job fail on unexpected? |
|---------|---------|-----------|-------|-------------------------|
| `feature/**`, `fix/**`, `hotfix/**`, `test/**` | `working` | `debug` | 1 VU × 1 iter (`ci-smoke`) | No (report-only) |
| `develop`, `dev` | `working` | `debug` | 1×1 | Yes |
| `main` / `master` | `full` | `load` | ramping VUs + 100 iters (`ci-load`) | Yes |

Execute goes to dig: `POST https://am-dev.asrax.in/qa/api/runs/execute` with explicit `dataset_profile` (do not rely on `branch.py` alone).

## Secrets

| Secret | Purpose |
|--------|---------|
| `SPT_CI_API_KEY` | Dig QA API key with **role=ci** (preferred) |
| `QA_AGENT_GATEWAY_TOKEN` | Fallback bearer if CI key unset |
| `ZOHO_CLIQ_SPT_WEBHOOK_URL` | Team Cliq channel (falls back to `QA_AGENT_CLIQ_WEBHOOK_URL` / `ZOHO_CLIQ_WEBHOOK_URL`) |
| `SPT_SMTP_HOST` / `PORT` / `USER` / `PASSWORD` / `FROM` | Email committer only |

Bootstrap dig key (example): set `SPT_BOOTSTRAP_KEYS` to include `ci:spt-ci:<secret>` or create via admin API keys UI with role `ci`.

## Notifications

Same report card → email (committer) + Cliq (channel). Notify is best-effort; SPT pass/fail still recorded if mail/Cliq fail.

## Manual test

```bash
# In am-qa-agents — simulate feature smoke
gh workflow run spt-on-commit.yml -f service=am-market-data -f git_ref=feature/spt-smoke

# Simulate main load (no merge required)
gh workflow run spt-on-commit.yml -f service=am-market-data -f git_ref=main
```

Or push a no-op under `am-market-data/` on a feature branch.
