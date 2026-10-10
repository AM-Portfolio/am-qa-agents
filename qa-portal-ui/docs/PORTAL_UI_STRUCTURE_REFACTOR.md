# QA portal UI — structure refactor (plan)

**Status:** awaiting review before any extract/split work  
**Package:** `qa-portal-ui` only  
**Stack:** keep `flutter_bloc` + `get_it` (no Riverpod)  
**Hard rule:** every Dart file ≤ **600 lines**  
**UI:** extract-only — no Specs IA / visual redesign

**TODO list (separate file):** [PORTAL_UI_STRUCTURE_REFACTOR_TODO.md](./PORTAL_UI_STRUCTURE_REFACTOR_TODO.md)

Related Cursor plan: `qa_ui_flutter_skills`.

---

## Goals

1. Install [Flutter-Skills](https://github.com/zakariaf/Flutter-Skills) + thin `am-qa-portal-ui` adapter for agents.
2. Bring all `lib/**/*.dart` files to ≤600 lines by **moving code into sibling files** (same behavior).
3. Freeze Specs Collections/Datasets/lazy tabs — do not redesign the shell again.
4. Shared widgets only when the same UI is extracted twice (pull, don’t push).

---

## Decisions (locked for this draft)

| Topic | Choice |
|---|---|
| Scope | `am-qa-agents/qa-portal-ui` only |
| State | Bloc/Cubit + get_it |
| Specs IA | Freeze |
| File size | Max 600 lines per `.dart` |
| Models | Typed models only if a split needs a clean boundary — not a portal-wide Map purge now |
| Backend / gitops / am-modern-ui | Out of scope |

Flutter-Skills to load (ignore Riverpod/Drift/ads/IAP):  
`flutter-architecture`, `project-structure-and-packages`, `widget-composition`, `scaffold-feature-module`, `ui-states-and-feedback`, `dart3-idioms-and-coding-standards`, `naming-conventions`, `async-safety`.

---

## Current offenders (>600 lines)

| Lines | File |
|---:|---|
| ~2295 | `lib/features/runs/presentation/pages/run_detail_page.dart` |
| ~1726 | `lib/features/specs/presentation/cubit/specs_cubit.dart` |
| ~803 | `lib/features/flows/presentation/cubit/flows_cubit.dart` |
| ~799 | `lib/features/specs/presentation/widgets/test_workspace.dart` |
| ~794 | `lib/features/profiles/presentation/pages/profiles_page.dart` |
| ~745 | `lib/features/services/presentation/pages/services_page.dart` |
| ~722 | `lib/features/execute/presentation/pages/execute_bar.dart` |
| ~713 | `lib/features/specs/presentation/datasets/specs_datasets_view.dart` |
| ~702 | `lib/features/services/presentation/widgets/coverage_board.dart` |
| ~694 | `lib/features/flows/presentation/widgets/flow_node_compose_card.dart` |
| ~688 | `lib/features/runs/presentation/pages/runs_page.dart` |
| ~671 | `lib/features/flows/presentation/widgets/credentials_manager.dart` |
| ~656 | `lib/features/ui_flows/presentation/cubit/ui_flows_cubit.dart` |

---

## Target folder structure

`+` = new from skills / extract splits. Unmarked = keep (often thinner).

```text
qa-portal-ui/
├── AGENTS.md                                    +
├── .cursor/skills/
│   ├── am-qa-portal-ui/SKILL.md                 +
│   └── flutter-* / widget-* / …                 +  Flutter-Skills
├── tool/check_max_lines.dart                    +  optional
├── docs/
│   ├── PORTAL_UI_STRUCTURE_REFACTOR.md          ← plan (this file)
│   └── PORTAL_UI_STRUCTURE_REFACTOR_TODO.md     ← TODO (separate)
└── lib/
    ├── main.dart / app.dart
    ├── core/                                    # same as today
    │   ├── config/  di/  network/  router/
    ├── shared/widgets/                          +  only if reused twice
    │   ├── portal_search_field.dart
    │   ├── portal_filter_chip.dart
    │   └── http_method_badge.dart
    └── features/
        ├── shell/ …
        ├── observability/ …
        ├── flow_graph/ …
        │
        ├── specs/                               # Wave A
        │   ├── data/specs_repository.dart
        │   ├── domain/{try_draft,openapi_fill}.dart
        │   └── presentation/
        │       ├── pages/specs_page.dart
        │       ├── cubit/
        │       │   ├── specs_state.dart
        │       │   ├── specs_cubit.dart         # facade ≤600
        │       │   ├── specs_cubit_catalog.dart +
        │       │   ├── specs_cubit_test.dart    +
        │       │   ├── specs_cubit_data.dart    +
        │       │   ├── specs_cubit_mcp.dart     +
        │       │   ├── specs_cubit_usecases.dart +
        │       │   └── specs_cubit_ensure.dart  +
        │       ├── shell/                       # keep IA
        │       ├── tabs/                        # keep
        │       ├── datasets/
        │       │   ├── specs_datasets_view.dart
        │       │   ├── datasets_versions_table.dart  +
        │       │   ├── datasets_rows_list.dart       +
        │       │   └── datasets_values_panel.dart    +
        │       └── widgets/
        │           ├── test_workspace.dart
        │           ├── test_request_panel.dart  +
        │           ├── test_response_panel.dart +
        │           ├── test_auth_panel.dart     +
        │           └── …
        │
        ├── runs/                                # Wave B
        │   └── presentation/
        │       ├── pages/
        │       │   ├── runs_page.dart
        │       │   └── run_detail_page.dart
        │       └── widgets/
        │           ├── run_detail_summary.dart  +
        │           ├── run_detail_graph.dart    +
        │           ├── run_detail_logs.dart     +
        │           └── run_detail_actions.dart  +
        │
        ├── flows/                               # Wave C
        ├── services/                            # Wave C
        ├── profiles/                            # Wave C
        ├── execute/                             # Wave C
        └── ui_flows/                            # Wave C
```

---

## Phases (summary)

| Phase | Work |
|---|---|
| 0 | Install Flutter-Skills + `am-qa-portal-ui` + `AGENTS.md` |
| 1 | Specs: split `specs_cubit`, `test_workspace`, `specs_datasets_view` ≤600 |
| 2 | Runs: split `run_detail_page` (+ `runs_page` if needed) |
| 3 | Remaining offenders (Flows → Services/Profiles/Execute → ui_flows) |
| 4 | Shared kit only if the same widget was extracted twice |

Track checkboxes in the [TODO file](./PORTAL_UI_STRUCTURE_REFACTOR_TODO.md).

---

## Acceptance

- Skills + adapter + `AGENTS.md` present  
- Zero `lib/**/*.dart` files with >600 lines  
- Specs still first-ready (APIs before OpenAPI); no intentional UX change  
- `dart analyze` clean on `qa-portal-ui`  

---

## Out of scope

- New Specs sidebar/tabs/IA or Datasets UX redesign  
- Portal-wide typed-model rewrite in one go  
- Riverpod migration  
- qa-agent Python, OpenAPI backends, gitops, am-modern-ui  
