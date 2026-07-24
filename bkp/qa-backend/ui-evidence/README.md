# AM UI Test Agent

Playwright + LangGraph agent for **am-modern-ui** domain smokes and release gates.

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # if present
npm test               # unit tests
```

## Domain smokes (in-process)

From `am-agents` root (needs Flutter app on `:9000`):

```bash
npm run ui-test:dashboard:local
npm run ui-test:portfolio:local
npm run ui-test:market:local
npm run ui-test:trade:local
npm run ui-test:doc:local
npm run ui-test:suite:smoke
```

## Profiles

| Profile | Coverage |
|---------|----------|
| AUTH_FLOW_MAIN | Login → `/app/dashboard` |
| DASHBOARD_SMOKE_FLOW | Deep-link dashboard |
| PORTFOLIO_SMOKE_FLOW | Deep-link portfolio overview |
| PORTFOLIO_TABS_FLOW | Tab sweep |
| MARKET_SMOKE_FLOW | all-indices + dashboard + heatmap |
| TRADE_SMOKE_FLOW | trade discovery |
| DOC_INTEL_SMOKE_FLOW | doc-processor + email-extractor |
| PROFILE_SMOKE_FLOW | profile + privacy |
| SUBSCRIPTION_SMOKE_FLOW | subscription |
| ADMIN_GATE_FLOW | analysis/ai-chat/lab redirects |

## API

- `POST /api/v1/test/run/auth`
- `POST /api/v1/test/run/profile` `{ profile, targetUrl? }`
- `POST /api/v1/test/run/suite` `{ suite: release_gate|smoke }`
- `GET /api/v1/test/profiles`

## Smoke defaults

`DESIGN_REVIEW_ENABLED=false`, `SELF_HEAL_ENABLED=false`, `PLAYWRIGHT_TRACE=on-failure`.

Docs: [TEST_DATA.md](docs/TEST_DATA.md), [QA_DOSSIER_CONTRACT.md](docs/QA_DOSSIER_CONTRACT.md).
