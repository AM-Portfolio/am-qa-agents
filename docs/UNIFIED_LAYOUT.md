# Unified layout

```text
am-qa-agents/
├── .code-intelligence.yaml    # GitNexus registration
├── .env.example
├── package.json               # wrappers: portal + agent test/build
├── docs/
├── qa-portal-ui/              # Flutter portal (+ .env.example)
└── qa-agent/                  # ONE backend / one pod
    ├── .am.yaml               # amctl / central-deploy
    ├── observability.yaml     # ServiceObservability (am.obs/v1)
    ├── .env.example
    ├── Dockerfile
    ├── helm/                  # universal-chart values (dev/preprod/prod + vault)
    ├── specs/                 # Specs / load / MCP (+ spt.yaml self-reg)
    ├── ui_evidence/           # Playwright UI (+ spt.yaml self-reg)
    ├── release_gate/          # Temporal release readiness
    ├── composition/           # merge routes + worker
    └── common/
```

## Runtime

```text
PYTHONPATH=qa-agent:qa-agent/release_gate
```

## Deploy contract

| Piece | Location |
|-------|----------|
| Image | `ghcr.io/am-portfolio/am-qa-agents` |
| Helm | `qa-agent/helm/values.yaml` + `values.{dev,preprod,prod}.yaml` + `vault-mappings.yaml` |
| Namespaces | `am-apps-dev` / `am-apps-preprod` / `am-apps-prod` |
| Traefik | `/spt-poc` + `/ui-test` → same Service |
| Catalog | `SPT_CATALOG_EXTERNAL` (product `spt.yaml` + self regs) |
| GitNexus | `.code-intelligence.yaml` (`group_path: agents/am-qa-agents`) |

Public paths (`/spt-poc`, `/ui-test`) and `SPT_*` env names are unchanged.
