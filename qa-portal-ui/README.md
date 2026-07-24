# QA Portal UI (Flutter)

Operator portal for **api-load** (Runs / Profiles / Specs / UI flows).

- **Look & feel:** [`am_design_system`](../../am-modern-ui/am_design_system) (same as core product)
- **HTML portal** (`static/`, `templates/`) still served by api-load at `/ui` until Flutter cutover

## Prerequisites

Sibling checkout required:

```
am-repos/
  am-modern-ui/          # design system + am_common
  am-qa-agents/
    qa-portal-ui/
```

## Run locally

```powershell
# Terminal A — api-load
cd ..\qa-backend\api-load
.\scripts\run-local.ps1

# Terminal B — Flutter portal
cd ..\..\qa-portal-ui
flutter pub get
flutter run -d chrome --web-port=8151 --dart-define=API_BASE=http://localhost:8150
```

Theme toggle is in the rail footer (uses product `ThemeCubit`).

## Build (cluster base-href)

```powershell
flutter build web --release --base-href=/spt-poc/ui/
```

## Layout

```
lib/
  core/          # di, config, network, router
  features/
    shell/       # operator NavigationRail (not product module nav)
    runs/
    profiles/
    execute/
    specs/       # stub — next
    ui_flows/    # stub — next
```

## CI

Workflow: `.github/workflows/qa-portal-ui.yml` (checks out `am-modern-ui` beside this repo).
