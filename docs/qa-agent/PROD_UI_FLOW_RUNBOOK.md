# Prod UI flow runbook

Read-only UI coverage for `https://am.asrax.in` via the ui-test-agent (`prod_ui_full` suite).

Live sidebars covered: Portfolio (overview / holdings / heatmap / baskets), Trade (all view tabs), Market user (dashboard / market-analysis) + non-admin gate. Never Add Trade, basket creator, doc upload, Market Admin/Developer mutating tools, or Demo Login.

## Prerequisites

- Test user credentials in Vault / local env (`TEST_USER_EMAIL`, `TEST_USER_PASSWORD`)
- Known prod `portfolio_id` for that user (`TEST_PORTFOLIO_ID` or `--portfolio-id`)
- Playwright-capable ui-test-agent (local or preprod/dev). Prod `/ui-test` ingress may stay disabled; point the agent at the prod **app** URL
- GrowthBook `subscription-page-enabled`: if off, treat `SUBSCRIPTION_SMOKE_FLOW` soft failures as acceptable caveats

## Run

From `am-qa-agents/qa-agent/ui_evidence` (or unified composition with UI evidence on PYTHONPATH):

```powershell
$env:TEST_USER_EMAIL="..."
$env:TEST_USER_PASSWORD="..."
$env:TEST_PORTFOLIO_ID="..."

python scripts/run_suite.py `
  --suite prod_ui_full `
  --url https://am.asrax.in `
  --login-mode credentials `
  --portfolio-id $env:TEST_PORTFOLIO_ID
```

`prod_ui_full` forces credentials when `--login-mode demo` is passed by mistake.

Smoke / release_gate (non-prod):

```powershell
python scripts/run_suite.py --suite smoke --url https://am-dev.asrax.in
python scripts/run_suite.py --suite release_gate --url https://am-dev.asrax.in
```

## Suite matrix

| Profile | TC | Prod |
|---------|----|------|
| `AUTH_FLOW_MAIN` | TC-AUTH-01 | Credentials only |
| `DASHBOARD_SMOKE_FLOW` | TC-DASH-01 | Read-only |
| `PORTFOLIO_SMOKE_FLOW` | TC-PORT-01 | Overview |
| `PORTFOLIO_TABS_FLOW` | TC-PORT-02 | overview, holdings, heatmap, baskets |
| `TRADE_SMOKE_FLOW` | TC-TRD-01 | Discovery |
| `TRADE_TABS_FLOW` | TC-TRD-02 | All view tabs; no Add Trade |
| `MARKET_USER_FLOW` | TC-MKT-01 | dashboard + market-analysis |
| `MARKET_GATE_FLOW` | TC-MKT-03 | admin/streamer → dashboard |
| `DOC_INTEL_SMOKE_FLOW` | TC-DOC-01 | View only; no upload |
| `PROFILE_SMOKE_FLOW` | TC-PRF-01 | Read-only |
| `SUBSCRIPTION_SMOKE_FLOW` | TC-SUB-01 | Skip/caveat if flag off |
| `ADMIN_GATE_FLOW` | TC-ADM-01 | Non-admin redirects |

Out of suite: `MARKET_DEV_FLOW` (admin explorers), `DOC_UPLOAD_FLOW`, Demo Login.

## Proof template

After a run, fill and keep with the suite JSON under the agent report dir:

| Field | Value |
|-------|-------|
| Date (UTC) | |
| Suite id | from `suite-*.json` |
| Target URL | `https://am.asrax.in` |
| Login mode | `credentials` |
| Portfolio id | |
| Decision | GO / GO_WITH_CAVEATS / NO_GO |
| Hard fails | |
| Soft fails | |
| Summary path | `suite-<id>.json` |
| Per-profile reports | list HTML/PDF paths |

Per-profile checklist (copy from suite JSON `results[]`):

| Profile | Status | Report | Soft fails |
|---------|--------|--------|------------|
| AUTH_FLOW_MAIN | | | |
| DASHBOARD_SMOKE_FLOW | | | |
| PORTFOLIO_SMOKE_FLOW | | | |
| PORTFOLIO_TABS_FLOW | | | |
| TRADE_SMOKE_FLOW | | | |
| TRADE_TABS_FLOW | | | |
| MARKET_USER_FLOW | | | |
| MARKET_GATE_FLOW | | | |
| DOC_INTEL_SMOKE_FLOW | | | |
| PROFILE_SMOKE_FLOW | | | |
| SUBSCRIPTION_SMOKE_FLOW | | | |
| ADMIN_GATE_FLOW | | | |

## Safety rules

- Do not click New Trade, Add Trade, Edit/Delete trade, basket creator, subscription purchase
- Do not open Market Admin / Developer Dashboard / Price Test on prod automation
- Do not upload documents on prod (`DOC_UPLOAD_FLOW` excluded)
- Prefer honest SKIPPED / soft WARN over fake COMPLETED
