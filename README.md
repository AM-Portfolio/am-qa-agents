# am-qa-agents

## Layout

| Path | Role |
|------|------|
| [`qa-agent/`](qa-agent/) | **One backend** — `specs` + `ui_evidence` + `release_gate` |
| [`qa-portal-ui/`](qa-portal-ui/) | Flutter operator portal (baked into image optionally) |
| [`docs/`](docs/) | Shared documentation |

See [`docs/UNIFIED_LAYOUT.md`](docs/UNIFIED_LAYOUT.md), [`docs/CONTRACTS.md`](docs/CONTRACTS.md), [`qa-agent/helm/README.md`](qa-agent/helm/README.md).

## Local

```powershell
cd am-qa-agents
pip install -e ".[all]"
Copy-Item qa-agent\.env.example qa-agent\.env
$env:PYTHONPATH = "$(Get-Location)\qa-agent;$(Get-Location)\qa-agent\release_gate"
$env:QA_AGENT_WORKER_ENABLED = "0"
python -m composition.main   # :8150

# Portal (separate terminal)
npm --prefix qa-portal-ui run get
npm --prefix qa-portal-ui run run:local
```

Or use root wrappers:

| Script | What |
|--------|------|
| `npm start` / `npm run backend:start` | Unified API on :8150 |
| `npm run api:smoke` | Live HTTP checklist (working / not) |
| `npm run test:flow` | api:smoke + pytest |
| `npm run ui:start` | Flutter portal :8151 → localhost:8150 |
| `npm run ui:start:dev` | Flutter → VPS `am-dev` SPT (`/spt-poc`) |
| `npm run vps:forward` | Port-forward Temporal `:7233` + Influx `:8086` via `VPS/VPS/kubeconfig.vps` |
| `npm run ui:get` / `ui:analyze` / `ui:build` | Portal deps / analyze / build |
| `npm run release:ops:drive` | Daily Drive pack (no UI/soak/Cliq) — see [`docs/qa-agent/RELEASE_REPORT.md`](docs/qa-agent/RELEASE_REPORT.md) |

n8n trigger (sibling repo **`am-n8n-workflows`**, add `f:\am-repos\am-repos\am-n8n-workflows` to the Cursor workspace): workflow **qa-release-ops** — Execute in n8n or POST `/webhook/qa-release-ops`.

### Local ↔ VPS lab

Default `kubectl` context `am-local` on `:6443` is often down; use the VPS kubeconfig for Kind on `203.174.22.129`:

```powershell
$env:KUBECONFIG = "F:\am-repos\am-repos\VPS\VPS\kubeconfig.vps"
npm run vps:forward   # leave running; wire TEMPORAL_HOST / INFLUXDB_URL in qa-agent/.env
```

| Dependency | VPS status | Local wire-up |
|------------|------------|---------------|
| **Playwright UI agent** | `am-ui-test-agent` in `am-apps-dev` — public `https://am-dev.asrax.in/ui-test` | Colocated `:8150` or set `SPT_UI_TEST_AGENT_URL` to that URL |
| **SPT / portal API** | `am-spt-poc` in `am-apps-dev` — `https://am-dev.asrax.in/spt-poc` | Local `:8150` or `npm run ui:start:dev` |
| **Temporal** | `temporal` ns healthy; UI `https://temporal.asrax.in` | gRPC via `vps:forward` → `TEMPORAL_HOST=127.0.0.1:7233`; set `QA_AGENT_WORKER_ENABLED=1` for release-readiness |
| **Influx** | `influxdb` in `infra` (bucket `load-testing-dev`) | `vps:forward` → `INFLUXDB_URL=http://127.0.0.1:8086` + token from `load-testing/am-spt-poc-influx` |
| **Qdrant** | Service exists; **StatefulSet replicas=0** (no endpoints → public 502) | Scale: `kubectl scale sts qdrant -n am-ai --replicas=1`, then `npm run vps:forward:qdrant` |

## Production deploy

1. Publish image: `.github/workflows/qa-agent.yml` (context `.`, dockerfile `qa-agent/Dockerfile`)
2. Deploy: `.github/workflows/deploy-qa-agent.yml` → **dev | preprod | prod**
3. Helm (universal-chart): `qa-agent/helm/values.yaml` + `values.<env>.yaml` + `vault-mappings.yaml`
4. Register surfaces: `qa-agent/specs/spt.yaml`, `qa-agent/ui_evidence/spt.yaml` (mount under `SPT_CATALOG_EXTERNAL`)
5. GitNexus: root `.code-intelligence.yaml` + `.github/workflows/code-intelligence.yml`

amctl config: [`qa-agent/.am.yaml`](qa-agent/.am.yaml). Observability: [`qa-agent/observability.yaml`](qa-agent/observability.yaml). Seed Vault at `apps/data/<env>/services/am-qa-agents`.
