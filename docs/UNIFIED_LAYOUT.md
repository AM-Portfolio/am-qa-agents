# Unified layout

```text
am-qa-agents/
├── qa-agent/              # ALL related backend (SPT + release-gate)
│   ├── composition/       # one process: HTTP + Temporal worker
│   ├── gateway/
│   ├── orchestrator/
│   ├── intelligence/
│   ├── learning/
│   ├── adapters/
│   ├── stores/
│   ├── spt/               # former api-load
│   ├── common/
│   ├── registry/, config/, catalog/
│   ├── helm/, Dockerfile
│   └── tests/, scripts/
├── ui_evidence/           # kept as-is (separate package)
├── qa-portal-ui/
├── bkp/                   # legacy qa-backend backup — ZERO deps on live code
└── docs/
```

- Live imports use `PYTHONPATH=qa-agent:.`
- `bkp/` must never be imported by `qa-agent` or `ui_evidence`
