# QA Portal Flutter — E2E checklist (E1–E20)

Run: api-load on `:8150` + `cd qa-portal-ui && npm run run` (Chrome `:8151`).

| # | Scenario | Pass? | Notes |
|---|----------|-------|-------|
| E1 | Boot → health chip **api ok** | | No DioException / CORS |
| E2 | Runs list shows rows | | Parser `runs` key |
| E3 | Filters status/service/env/search/test_type/from/to + Apply | | |
| E4 | Open running run → live progress poll | | |
| E5 | Stop from detail / execute bar | | |
| E6 | Artifacts download / MinIO link | | |
| E7 | Inspector failed-only + Request/Response tabs + Save payload | | |
| E8 | Execute k6 debug 1×1 → detail | | |
| E9 | Execute playwright + UI flow | | Needs ui-test-agent |
| E10 | Profiles list/edit/save + Run with this profile | | |
| E11 | Specs Try Send with try-token | | |
| E12 | Specs API multi-select + Run load | | Needs matching config |
| E13 | Specs payload Ensure / Activate / Build / Ensure-working / MCP | | |
| E14 | UI flows agent chip + CRUD + Run flow | | |
| E15 | Profile avatar → Profile & Settings | | |
| E16 | Clear cache | | |
| E17 | Execute presets + API picker + OpenAPI version | | |
| E18 | Run detail Re-run / Debug / Save as config / Export | | |
| E19 | Deep-links `?run=` `?config=` `?spec=` | | |
| E20 | Pagination Prev/Next on Runs | | |

## Serve cutover smoke

```powershell
cd qa-portal-ui
npm run build:local
# api-load .env:
# SPT_PORTAL_FLUTTER=true
# SPT_PORTAL_FLUTTER_DIR=../../qa-portal-ui/build/web
# ROOT_PATH=
```

Open http://localhost:8150/ui/ — SPA loads, APIs same-origin.

## Sign-off

- Tester:
- Date:
- Environment: local / cluster
- Blockers:
