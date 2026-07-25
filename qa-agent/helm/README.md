# Helm for am-qa-agents

CI deploy (`deploy-qa-agent.yml`) uses **am-pipelines universal-chart** and layers:

1. `values.yaml`
2. `vault-mappings.yaml`
3. `values.<env>.yaml` (`dev` | `preprod` | `prod`)

Do not rely on a local `Chart.yaml` for production deploys.

Seed Vault path per env (example):

```text
apps/data/<env>/services/am-qa-agents
```

with keys listed in `vault-mappings.yaml` under `qa-agent.mappings`.

Product OpenAPI registrations are **not** baked into the image — mount ConfigMaps of `spt.yaml` files at `SPT_CATALOG_EXTERNAL` (`/catalog-external`).

`values.yaml` projects `spt-catalog-am-{analysis,gateway,mcp-server}` ConfigMaps (same namespace as the deploy). Publish them with:

```bash
python scripts/publish-spt-catalogs.py --namespace load-testing --namespace am-apps-dev
```

from **am-core-services** (CI: `qa-agent-notify.yml` does this **before** `POST /release-readiness`).
