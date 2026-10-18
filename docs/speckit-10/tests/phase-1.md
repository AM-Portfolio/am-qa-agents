# Tests — Phase 1 (CI gates + change-driven pipeline)

**Repo:** `AM-Portfolio/am-specs` · **Verify:** [VERIFY.md](../VERIFY.md) + [PIPELINE.md](../PIPELINE.md) + **GitHub MCP**.

## Gates

- [ ] openapi-generator pinned in CI
- [ ] `--require-typed` fail-hard
- [ ] validate requires non-empty typed for focus/enabled
- [ ] ENABLEMENT/SCORECARD/CONSUMING aligned

## Change-driven (critical)

- [ ] `detect-changed-services` job exists
- [ ] PR touching only `services/<id>/openapi.yaml` → generate/build jobs run for **that id only** (GitHub MCP logs)
- [ ] PR with no `services/**` changes → generate/build **skipped**
- [ ] `workflow_dispatch` still supports force `service=` and rare `all_enabled`

## GitHub MCP

- [ ] validate **success** on Phase 1 PR
- [ ] Record PR URL + run URLs
