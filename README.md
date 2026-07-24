# am-qa-agents

Canonical **QA agents monorepo** for AM Portfolio.

Remote: https://github.com/AM-Portfolio/am-qa-agents

## Packages (2)

| Package | Role |
|---------|------|
| [`qa-portal-ui/`](qa-portal-ui/) | Operator portal: **Flutter** (design system) + legacy HTML until cutover |
| [`qa-backend/`](qa-backend/) | Complete backend QA engines |

### Backend modules

| Module | Image / release | Role |
|--------|-----------------|------|
| [`qa-backend/api-load`](qa-backend/api-load/) | `am-spt-poc` | k6, OpenAPI payloads, FastAPI APIs; serves portal |
| [`qa-backend/ui-evidence`](qa-backend/ui-evidence/) | `am-ui-test-agent` | Playwright testing |
| [`qa-backend/release-gate`](qa-backend/release-gate/) | `am-qa-agent` | Release GO/NO_GO dossier (Temporal) |

**Outside this repo:** product SPA [`am-modern-ui`](../am-modern-ui).

## Local

```powershell
# API load (still serves HTML /ui)
cd qa-backend\api-load
.\scripts\run-local.ps1   # http://localhost:8150/ui

# Flutter operator portal (design system)
cd ..\..\qa-portal-ui
flutter pub get
flutter run -d chrome --web-port=8151 --dart-define=API_BASE=http://localhost:8150
```

## CI

GitHub Actions live in [`.github/workflows/`](.github/workflows/) — names match packages (`api-load`, `ui-evidence`, `release-gate`). See [docs/GITHUB_PIPELINES.md](docs/GITHUB_PIPELINES.md).

## Docs

- [docs/PLAN_ORGANIZE_AUTH_GO.md](docs/PLAN_ORGANIZE_AUTH_GO.md) — auth + GO/NO_GO organize plan
- [docs/GITHUB_PIPELINES.md](docs/GITHUB_PIPELINES.md) — workflow map
