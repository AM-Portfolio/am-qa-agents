# Vault layout for am-qa-agents (dev pilot)

## Three layers

| Layer | Path shape | Action |
|-------|------------|--------|
| Infra stores | `apps/data/{env}/infra/{store}` (+ legacy `apps/{env}/infra/*`) | Keep forever |
| Legacy services | `apps/{env}/services/<name>` | Leave as-is (scheduler, billing, …) |
| Runtime domains | `apps/data/{env}/runtime/modules/<domain>` | New — pilot `qa` |

## Pilot

- Seeded: `apps/data/dev/runtime/modules/qa`
- Helm: [helm/values.dev.yaml](../helm/values.dev.yaml) `qa-agent.path`
- ACL: existing `am-auth-policy` `path "apps/data/*"` already covers runtime
- **Do not** create per-Deployment paths (`modules/scheduler`, `modules/lago`, …)

## Domains (later)

`market` (incl. scheduler), `billing` (subscription+lago), `comms`, `core`, `agents`, `qa`, …

## Operator seed

```bash
# Prefer API enrichment used in Phase 2; shell helper:
# scripts/seed-runtime-qa-vault.sh  (needs jq in vault pod)
```

**KV path note (injector):** Helm annotation `apps/data/dev/runtime/modules/qa` is resolved by Vault Agent to API `GET /v1/apps/data/dev/runtime/modules/qa` (KV path `dev/runtime/modules/qa`), same pattern as working `am-analysis`. Also keep a copy at `apps/data/data/dev/runtime/modules/qa` for `vault kv get apps/data/dev/runtime/modules/qa` CLI SoT. Seed both when writing.

Source `apps/dev/services/am-ui-test-agent` and related KVs are **not** deleted.
