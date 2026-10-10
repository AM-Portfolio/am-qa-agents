# AM agent context (qa-portal-ui)

Flutter web operator portal for AM QA (Specs, Flows, Runs, Services, …).

## Skills

- **Required for this package:** `.cursor/skills/am-qa-portal-ui/SKILL.md`
- **Flutter craft (installed locally):** `.cursor/skills/` from [zakariaf/Flutter-Skills](https://github.com/zakariaf/Flutter-Skills) — load architecture / widget-composition / etc. as listed in the adapter skill
- Do **not** use `am-flutter-ui` package paths here (those are am-modern-ui)

## Hard rules

1. Keep **flutter_bloc + get_it** (no Riverpod migration unless explicitly requested).
2. **Max 600 lines** per `lib/**/*.dart` file. Check: `dart run tool/check_max_lines.dart`
3. Specs IA: OpenAPI rail = Test/Swagger/MCP/SDK/Use cases; Datasets = `/datasets`; secondary = API. Main nav home = Dashboard (not Services).
4. Extract-only structure refactors — same UX, sibling files for fat classes.
5. Never commit secrets. Run builds/tests in the IDE terminal.

## Structure docs

- [docs/PORTAL_UI_STRUCTURE_REFACTOR.md](docs/PORTAL_UI_STRUCTURE_REFACTOR.md)
- [docs/PORTAL_UI_STRUCTURE_REFACTOR_TODO.md](docs/PORTAL_UI_STRUCTURE_REFACTOR_TODO.md)
