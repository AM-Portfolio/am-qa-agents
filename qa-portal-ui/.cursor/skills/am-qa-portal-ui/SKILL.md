---
name: am-qa-portal-ui
description: Work on am-qa-agents qa-portal-ui (Flutter web operator portal). Use when editing Specs, Flows, Runs, Services, Profiles, Execute, or portal shell. Keep flutter_bloc + get_it; max 600 lines per Dart file; do not apply am-modern-ui package paths.
---

# am-qa-portal-ui

Operator portal package: `am-qa-agents/qa-portal-ui` only.

## Stack (locked)

- **State / DI:** `flutter_bloc` Cubit + `get_it` — **not** Riverpod
- **Routing:** existing `go_router` under `lib/core/router/`
- **Design:** consume `am_design_system` (path dep); do not invent a second design system
- **Specs IA:** main Datasets (`/datasets`); OpenAPI rail = Test / Swagger / MCP·AI / SDK / Use cases; secondary = API list. Home = Dashboard (`/dashboard`).

## Hard rules

1. **≤600 lines** per `lib/**/*.dart` file (aim ~550 when editing). Split by extract/move, not by rewriting UX.
2. Do **not** follow `am-flutter-ui` paths (`am_app` / `am_common`) — that skill is for am-modern-ui.
3. No new REST/backend contracts for structure refactors.
4. Preserve Specs first-ready behavior (APIs paint before OpenAPI/tools/overview).

## Flutter-Skills to load (map Notifier → Cubit)

When restructuring or adding features, also load:

- `flutter-architecture`
- `project-structure-and-packages`
- `widget-composition`
- `scaffold-feature-module`
- `ui-states-and-feedback`
- `dart3-idioms-and-coding-standards`
- `naming-conventions`
- `async-safety`

Ignore Riverpod-first examples; use Cubit + constructor injection instead.

## Feature layout

```text
lib/features/<name>/
  data/           # repository
  domain/         # models + pure helpers
  presentation/
    cubit/        # state + orchestrator ≤600; helpers in siblings
    pages/        # route entry ≤600
    widgets/      # small widgets
```

Shared portal chrome only in `lib/shared/` when the same widget is extracted twice.

## Docs

- Plan: `docs/PORTAL_UI_STRUCTURE_REFACTOR.md`
- Todos: `docs/PORTAL_UI_STRUCTURE_REFACTOR_TODO.md`
