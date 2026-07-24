# qa-backend

Complete backend QA engines for the [am-qa-agents](../) monorepo.

| Module | Role |
|--------|------|
| [api-load](api-load/) | k6, payloads, APIs (`am-spt-poc`) |
| [ui-evidence](ui-evidence/) | Playwright (`am-ui-test-agent`) |
| [release-gate](release-gate/) | GO/NO_GO dossier (`am-qa-agent`) |

Operator portal HTML/JS lives in sibling [`qa-portal-ui`](../qa-portal-ui/), not here.
