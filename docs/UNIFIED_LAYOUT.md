# Unified layout

```text
am-qa-agents/
├── qa-agent/              # ONE backend tree
│   ├── composition/       # HTTP + Temporal worker
│   ├── gateway/           # release-gate HTTP
│   ├── orchestrator/
│   ├── intelligence/
│   ├── learning/
│   ├── adapters/
│   ├── spt/               # former api-load
│   ├── ui_evidence/       # Playwright UI agent
│   ├── common/
│   ├── registry/, config/, catalog/
│   ├── helm/, Dockerfile
│   └── tests/, scripts/
├── qa-portal-ui/
├── bkp/                   # legacy — ZERO deps
└── docs/
```

Live imports: `PYTHONPATH=qa-agent`.
