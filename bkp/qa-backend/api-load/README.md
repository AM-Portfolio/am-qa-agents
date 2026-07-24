# AM Test Agent

Unified test agent for **API load (k6)**, **UI (Playwright)**, and **mixed** suites — profiles, OpenAPI, Grafana, and agent-driven runs in one portal.

Formerly the SPT load portal (`am-spt-poc`); same deploy path, broader capabilities.

## Quick start (local portal — preferred for UI work)

```powershell
cd F:\am-repos\am-repos\am-qa-agents\qa-backend\api-load
.\scripts\run-local.ps1
```

1. Opens **http://localhost:8150/ui** (HTML by default; uvicorn `--reload`)
2. Uses `.env` for identity login; set `DEFAULT_ENVIRONMENT=dev` (product URLs derive from it)
3. **Flutter portal (recommended for operator work):** see [`qa-portal-ui`](../../qa-portal-ui/) — `flutter run` with `API_BASE`, or build web + `SPT_PORTAL_FLUTTER=true`
4. Use **APIs** / Execute to pick a profile, **Run test**, **Stop** to cancel a live run
5. For **Playwright UI**: set type **Playwright**, pick a flow. Local: `SPT_UI_TEST_AGENT_URL=http://localhost:8130`. Cluster: derived as `https://{host}/ui-test` from `APP_ENV`.

**Flutter cutover:** set `SPT_PORTAL_FLUTTER=true` and `SPT_PORTAL_FLUTTER_DIR` to `qa-portal-ui/build/web` (see `.env.example`). Docker: `Dockerfile.flutter-artifact` or `Dockerfile.flutter-sdk`.

**Cluster env:** Helm only needs `APP_ENV` + `ROOT_PATH` — analysis/identity/ui-test URLs are derived (see [docs/DEPLOY.md](../../docs/DEPLOY.md)).

See [PRODUCTION-READINESS.md](PRODUCTION-READINESS.md) before scaling beyond a single replica.

```powershell
copy .env.example .env   # set SPT_AUTH_PASSWORD
# K6_BIN=./vendor/bin/k6.exe on Windows (script downloads if missing)
```

### Manual local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8150
```

## Quick start (legacy smoke scripts)

```powershell
cd F:\am-repos\am-repos\am-agents\poc\spt
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env — set OCTOPERF_MCP_URL and optional token/workspace/project IDs

# MCP ping
python scripts/ping.py

# Full smoke (7 steps)
python scripts/smoke_test.py

# HTTP API
uvicorn app.main:app --port 8150
curl http://localhost:8150/ping
curl -X POST http://localhost:8150/smoke
```

## Preprod Kubernetes deploy (only when sharing UI)

**Namespace:** `load-testing` (isolated from `am-apps-preprod` — shared app namespace).

Deploy only after local verify:

```powershell
.\scripts\vps-build-load.ps1
.\scripts\deploy-dev.ps1 -SkipBuild -SkipPush
```

Portal: https://am.asrax.in/spt-poc/ui  
Grafana: https://grafana.asrax.in/d/spt-load-testing/spt-load-testing (AM / Platform)  
Metrics: [docs/METRICS.md](docs/METRICS.md) — Influx `load-testing-dev`, requires `INFLUXDB_TOKEN` secret `am-spt-poc-influx`.

### 1. Install OctoPerf (optional — or use SaaS MCP)

```powershell
$env:KUBECONFIG = "F:\am-repos\am-repos\VPS\VPS\kubeconfig.vps"   # VPS/VPS/kubeconfig.vps
F:\am-repos\am-repos\am-infra\k8s\load-testing\octoperf\install.ps1
```

### 2. Vault secrets

Create `apps/data/preprod/services/am-spt-poc` in Vault:

| Key | Example |
|-----|---------|
| `OCTOPERF_MCP_URL` | `https://api.octoperf.com/mcp` or in-cluster URL |
| `OCTOPERF_MCP_TOKEN` | OAuth token if required |
| `OCTOPERF_WORKSPACE_ID` | from OctoPerf UI |
| `OCTOPERF_PROJECT_ID` | from OctoPerf UI |
| `POC_TARGET_URL` | `https://httpbin.org/get` |

### 3. Deploy spt-poc (recommended — native, no Docker/Vault)

```powershell
# Uses VPS/VPS/kubeconfig.vps → namespace load-testing
.\scripts\deploy-preprod-native.ps1
```

**Option B — helm + Docker image** (when image is built):

```powershell
# Uses VPS/VPS/kubeconfig.vps by default (kind-am-preprod @ 203.174.22.129)
.\scripts\deploy-preprod.ps1 -ImageTag local-poc -LocalPoc
```

**Option C — vault + secrets (production-like preprod):**

```powershell
.\scripts\deploy-preprod.ps1 -ImageTag <ghcr-tag> -SkipBuild
```

Apply ingress strip-prefix (once per cluster):

```powershell
$env:KUBECONFIG = "F:\am-repos\am-repos\VPS\VPS\kubeconfig.vps"
kubectl apply -f F:\am-repos\am-repos\am-infra\k8s\ingress-routing.yaml
```

### 4. Verify in preprod

```bash
curl https://am.asrax.in/spt-poc/health
curl https://am.asrax.in/spt-poc/ping
curl -X POST https://am.asrax.in/spt-poc/smoke
```

### 5. Document result

Update [POC-RESULT.md](./POC-RESULT.md). **Do not start Phase 1 until PASS.**

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness |
| `/ready` | GET | Readiness + MCP URL |
| `/ping` | GET | MCP connect + list tools |
| `/smoke` | POST | Full Phase 0 smoke test |
| `/config` | GET | Non-secret config preview |

## Files

```
poc/spt/
├── app/              # FastAPI + MCP client + OctoPerf ops
├── k6/               # smoke-get.js
├── playwright/       # smoke-navigate.spec.ts
├── helm/             # universal-chart values
├── scripts/          # ping, smoke_test, deploy-preprod
├── Dockerfile
└── POC-RESULT.md
```
