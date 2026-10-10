# QA portal UI — structure refactor TODO (review)

**Plan doc (separate):** [PORTAL_UI_STRUCTURE_REFACTOR.md](./PORTAL_UI_STRUCTURE_REFACTOR.md)  
**Status:** done (extract-only; LOC gate green).

---

## Your review (blocking)

- [x] I read the plan doc (folder structure, ≤600 rule, Specs IA freeze)
- [x] I accept the decisions in that plan
- [x] Approve proceed → tell the agent “go” / “execute the plan”

---

## Execution TODO (after approve)

| # | Status | Todo |
|---|---|---|
| 0 | Done | Finish review checklist above |
| 1 | Done | Install Flutter-Skills into `qa-portal-ui/.cursor/skills` + write `am-qa-portal-ui` adapter + `AGENTS.md` |
| 2 | Done | Add ≤600-line house rule (`AGENTS.md` + optional `tool/check_max_lines.dart`) |
| 3 | Done | Wave A — Specs extract only: `specs_cubit`, `test_workspace`, `specs_datasets_view` → each ≤600 |
| 4 | Done | Wave B — Runs extract: `run_detail_page` (+ `runs_page` if needed) → ≤600 |
| 5 | Done | Wave C — Remaining offenders (Flows → Services / Profiles / Execute → ui_flows) |
| 6 | Skipped | Shared kit (`lib/shared/widgets`) — no duplicate extract earned yet |

---

## Done when

- [x] Skills + adapter + `AGENTS.md` present  
- [x] Zero `lib/**/*.dart` files with >600 lines (`dart run tool/check_max_lines.dart`)  
- [x] Specs still first-ready; no intentional UX change (extract-only)  
- [x] `dart analyze lib` — no errors (infos/deprecations remain)  
