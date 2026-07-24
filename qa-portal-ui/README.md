# QA Portal UI (Flutter)

Operator portal for **api-load** — Flutter operator UI (design system + feature modules).

- **Look & feel:** [`am_design_system`](../../am-modern-ui/am_design_system)
- **HTML** (`static/`, `templates/`) remains the fallback when `SPT_PORTAL_FLUTTER=false` (default)

## Features

| Area | Status |
|------|--------|
| Shell + theme | ThemeCubit, health, Grafana/MinIO, clear-cache |
| Runs list/detail | Filters, poll, stop, live, Grafana, inspector, artifacts |
| Execute bar | Profile sync, type, VUs/calls, reports, UI flow/suite, stop |
| Profiles | List + create/edit/delete + bench fields |
| OpenAPI / Specs | Catalog, API list, Try with try-token |
| UI flows | Flows/suites catalog + create/edit/delete + steps JSON + Run/Reset |
| Execute bar | Presets, API picker, OpenAPI version, audience lock |
| Specs | Load selection, payload sets, build/ensure/MCP |
| Run detail | Re-run, debug, save-as-config, export, inspector panes |
| Deep links | `?run=` `?config=` `?spec=` |
| E2E | [docs/E2E_CHECKLIST.md](docs/E2E_CHECKLIST.md) |

## Run locally

```powershell
# Terminal A — unified qa-agent backend
cd ..\..
$env:PYTHONPATH = "$(Get-Location)\qa-agent"
$env:QA_AGENT_WORKER_ENABLED = "0"
python -m composition.main   # http://localhost:8150

# Terminal B — Flutter (npm wrappers)
cd qa-portal-ui
npm run get
npm run run          # chrome :8151 → API http://localhost:8150
```

| Script | What it does |
|--------|----------------|
| `npm run get` | `flutter pub get` |
| `npm run run` / `run:local` | Dev Chrome on `:8151` against local api-load |
| `npm run run:cluster` | Dev against cluster `/spt-poc` API |
| `npm run build` / `build:local` | `build/web` with `--base-href=/ui/` |
| `npm run build:cluster` | `--base-href=/spt-poc/ui/` |
| `npm run analyze` / `test` / `clean` | Flutter analyze / test / clean |

### Serve Flutter from api-load

```powershell
npm run build:local
# .env in api-load:
# SPT_PORTAL_FLUTTER=true
# SPT_PORTAL_FLUTTER_DIR=../../qa-portal-ui/build/web
# ROOT_PATH=

# Cluster image path:
npm run build:cluster
# ROOT_PATH=/spt-poc
# SPT_PORTAL_FLUTTER=true
```

## Layout

```
lib/core/            # di, config, network, router
lib/features/
  shell/ runs/ profiles/ execute/ specs/ ui_flows/
```
