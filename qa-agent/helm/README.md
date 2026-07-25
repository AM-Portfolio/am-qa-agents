# Helm for am-qa-agents

CI deploy (`deploy-qa-agent.yml`) uses **am-pipelines universal-chart** and layers:

1. `values.yaml`
2. `vault-mappings.yaml`
3. `values.<env>.yaml` (`dev` | `preprod` | `prod`)

Do not rely on a local `Chart.yaml` for production deploys.

## Vault (domain paths — not per-service)

| Env | `qa-agent` alias path |
|-----|------------------------|
| **dev** | `apps/data/dev/runtime/modules/qa` |
| preprod / prod | `apps/data/<env>/services/am-qa-agents` until those envs adopt `runtime/modules/qa` |

Keys: see `vault-mappings.yaml` under `qa-agent.mappings`. Seed script: `scripts/seed-runtime-qa-vault.sh` (operator; copies from legacy sources — does **not** delete `services/*`).

Shared aliases (`otel`, `llm`, `identity`) keep existing infra/service paths. Do **not** create `modules/scheduler`, `modules/billing`, etc. — those fold into domain modules later (`market`, `billing`, …).

`am-auth-policy` already allows `apps/data/*` read — covers `runtime/modules/*`.

## SPT catalogs (any service, zero Helm churn)

Product OpenAPI / load registrations are **not** baked into the image.

| Piece | Role |
|-------|------|
| `spt-catalog-bundle` | **Only** volume mounted at `/catalog-external` — every `services/*/spt.yaml` as `<service>.yaml` |
| `spt-catalog-<service>` | Still published for traces/tooling; **not** listed in Helm |
| `SPT_CATALOG_EXTERNAL` | `/catalog-external` |

Adding the 40th (or 400th) service = new `spt.yaml` + publish script. **No** `values.yaml` edit.

```bash
# from am-core-services
python scripts/publish-spt-catalogs.py --namespace load-testing --namespace am-apps-dev
```

CI (`qa-agent-notify.yml`) runs this **before** `POST /release-readiness`.

Constraint: one ConfigMap ≤ **1 MiB**. Typical `spt.yaml` files fit dozens of services; if the bundle approaches the limit, split by domain later — still no per-service projected entries.
