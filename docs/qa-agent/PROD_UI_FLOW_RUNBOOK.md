# Prod UI flow runbook

Read-only UI coverage for `https://am.asrax.in` via the ui-test-agent (`prod_ui_full` suite).

Live sidebars covered: Portfolio (overview / holdings / heatmap / baskets), Trade (all view tabs), Market user (dashboard / market-analysis) + non-admin gate. Never Add Trade, basket creator, doc upload, Market Admin/Developer mutating tools, or Demo Login.

## Prerequisites

- Test user credentials in Vault / local env (`TEST_USER_EMAIL`, `TEST_USER_PASSWORD`)
- Optional prod `portfolio_id` (`TEST_PORTFOLIO_ID` or `--portfolio-id`). If null/empty, portfolio and trade flows still run verification on list/legacy routes (`/app/portfolio/...` without `{id}`); deep-link `{id}` paths are skipped with a console note
- Playwright-capable ui-test-agent (local or preprod/dev). Prod `/ui-test` ingress may stay disabled; point the agent at the prod **app** URL
- GrowthBook `subscription-page-enabled`: if off, treat `SUBSCRIPTION_SMOKE_FLOW` soft failures as acceptable caveats

## Run (short npm UI dispatcher)

From `am-qa-agents` root, with `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` in `.env` (`TEST_PORTFOLIO_ID` optional):

```powershell
npm run ui:list              # aliases
npm run ui                   # interactive pick
npm run ui -- auth
npm run ui -- portfolio --open-report
npm run ui -- core           # auth→dashboard→portfolio→trade→market
npm run ui -- prod           # full prod_ui_full suite
npm run ui:pack              # same as release:report:prod (pack + Sheet)
```

Evidence (HTML/JSON/PDF) lands under `ui-reports/`. Screenshots go to
`ui-reports/screenshots/{prefix}-{YYYYMMDD-HHMMSS}-{shortId}/` (e.g. `auth-20260806-110930-0f899509/`)
with files like `003-111005-login-form-visible.png`. The HTML report titles each shot as `[auth] ...`.


`prod_ui_full` / credentials login is the default when `TEST_ENVIRONMENT=prod`.

### Low-level (optional)

```powershell
$env:TEST_USER_EMAIL="..."
$env:TEST_USER_PASSWORD="..."
$env:TEST_PORTFOLIO_ID="..."

python scripts/with_pythonpath.py python qa-agent/ui_evidence/scripts/run_suite.py `
  --suite prod_ui_full `
  --url https://am.asrax.in `
  --login-mode credentials `
  --portfolio-id $env:TEST_PORTFOLIO_ID
```

`prod_ui_full` forces credentials when `--login-mode demo` is passed by mistake.

Smoke / release_gate (non-prod):

```powershell
npm run ui -- smoke --url https://am-dev.asrax.in
python scripts/with_pythonpath.py python qa-agent/ui_evidence/scripts/run_suite.py --suite release_gate --url https://am-dev.asrax.in
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
