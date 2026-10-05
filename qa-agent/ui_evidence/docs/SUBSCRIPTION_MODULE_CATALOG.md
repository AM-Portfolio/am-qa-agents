# Subscription module catalog (mapping SoT)

Productized **subscription-only** QA: backend API + modern-ui. No market/trade/doc-intel/full-auth.

Machine index: [`../catalog/subscription_module.yaml`](../catalog/subscription_module.yaml)

## Mapping

| Concern | Maps to |
|---------|---------|
| Suite id | `subscription_module` |
| API pack | `subscription` (`subscription_api_flows` + OpenAPI sweep) |
| Git paths that arm CI | `am-platform/am-subscription/**`, workflow files in catalog `trigger_paths` |
| Backend services | **am-subscription** (primary), **am-identity** (login JWT only) |
| UI surface | `/app/subscription` — `SUB_UI_*` + `SUBSCRIPTION_SMOKE_FLOW` |
| Portal | Specs Runs via release-ops `tracking_id` + `bridge_suite_profile_run` |
| Combined report | `ui_evidence/data/reports/api-test/subscription-module-complete-latest.html` |
| Ops start | GitHub Action `am-platform/.github/workflows/subscription-qa-on-main.yml` → `POST /qa/v2/releases/ops/start` with `suite=subscription_module`, `api_pack=subscription` (not n8n) |

## UI profiles

| Profile | What |
|---------|------|
| `SUB_UI_OPEN` | Login → open subscription page |
| `SUB_UI_PLANS` | Plan cards / Free / Pro / Upgrade |
| `SUB_UI_TIME_LEFT` | Trial / expires / time-left copy |
| `SUBSCRIPTION_SMOKE_FLOW` | Prod sidebar subscription smoke |

## API flows

| Flow | What |
|------|------|
| `FLOW_SUBSCRIPTION_LOGIN` | `POST /auth/login` (SPT creds) → tokens |
| `FLOW_SUBSCRIPTION` | health / plans / me (+ `/ai/subscription/plans` fallback) |

Sweep: OpenAPI tools for `am-subscription` only (HTML swagger → skip, not hard fail).

## How to run locally

```bash
cd qa-agent
set PYTHONPATH=.
python -u ui_evidence/scripts/run_subscription_module_complete.py
python -u ui_evidence/scripts/run_subscription_module_complete.py --skip-ui
python -u ui_evidence/scripts/run_suite.py --suite subscription_module --login-mode credentials
```

## Merge → portal (GitHub only)

Enablement is the `am-platform` workflow — no n8n import or manual webhook:

1. Push/merge to `main` touching `am-subscription/**` (or the workflow files listed in `trigger_paths`), **or**
2. Actions → **Subscription QA on main** → Run workflow (`workflow_dispatch`).

Requires repo secrets/vars: `QA_AGENT_GATEWAY_TOKEN`, optional `QA_AGENT_GATEWAY_BASE`. Results appear under Specs portal Runs via `tracking_id`.
