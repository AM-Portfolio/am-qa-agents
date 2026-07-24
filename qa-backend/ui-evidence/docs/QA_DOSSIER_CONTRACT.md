# QA dossier contract (ui-test-agent → qa-agent)

ui-test-agent emits UI evidence only. qa-agent owns the release GO/NO_GO dossier.

## Suite summary JSON (`suite-{id}.json`)

```json
{
  "suiteId": "uuid",
  "suite": "release_gate",
  "decision": "GO | GO_WITH_CAVEATS | NO_GO",
  "targetUrl": "https://...",
  "hard_fail_count": 0,
  "soft_fail_count": 0,
  "results": [
    {
      "profile": "PORTFOLIO_SMOKE_FLOW",
      "status": "COMPLETED",
      "error": null,
      "report": "/path/to/report.html",
      "duration_ms": 12345,
      "soft_failures": 0
    }
  ]
}
```

## Single-run result keys

`testId`, `status`, `profile`, `report`, `trace`, `failures`, `soft_failures`, `console_errors`, `duration_ms`

## Ownership

| Producer | Artifact |
|----------|----------|
| ui-test-agent | HTML report, suite JSON, Playwright trace |
| SPT | Load/API evidence |
| qa-agent | Mixed release dossier |

Do not fold SPT or UI evidence generation into qa-agent.
