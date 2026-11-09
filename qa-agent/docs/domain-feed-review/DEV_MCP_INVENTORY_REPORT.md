# Dig (dev) QA — flow vars, tokens, datasets report

- Base: `https://am-dev.asrax.in/qa`
- Portal: `https://am-dev.asrax.in/qa/ui`
- Dig image (last successful roll): `ghcr.io/am-portfolio/am-qa-agents:sha-flowvars-202611081614`
- Store: sqlite (ephemeral on dig pod; re-seed after roll)

## Root causes fixed

1. **Literal `{{symbol}}` / `{{exchange}}`** — flow `body_override` reintroduced disk templates; dig had no `AM_SPECS_DATASETS_PATH`, so run-time seed was empty.
2. **Missing Bearer** — `auth: true` nodes without login/`capture_tokens` never set `access_token`.
3. **Missing chain inputs** — IPO/watchlist path_params used `{{ipoId}}` / `{{watchlistId}}` without `bind_path` on `dg_*` sync.
4. **Search 400 `Unrecognized field "symbols"`** — live `InstrumentSearchCriteria` (Jackson fail-on-unknown) accepts `queries` / `tradingSymbols` only, **not** `symbols`. Packs + sync now strip `symbols`; search step uses `tradingSymbols` + capture `$[0].trading_symbol`.
5. **Search step dropped on import** — PowerShell rewrite left a UTF-8 BOM on the search cross_flow JSON; loader used `utf-8` and silently skipped the file → flow had only fundamentals. Loader now uses `utf-8-sig`.

## Code / pack changes

| Area | Change |
|------|--------|
| `specs/flows/runner.py` | `_seed_default_vars`, `_merge_body_override`, `_identity_login` auto Bearer |
| `specs/data_gen/workflows.py` | seed `variables`, strip search `symbols`, capture `trading_symbol`, bind synthesis |
| `specs/data_gen/pack.py` | `utf-8-sig` example load |
| `specs/data_gen/import_svc.py` | pass env into sync; `patch_payload_set` env |
| `specs/tests/test_flow_runner_vars.py` | symbols strip + capture assertions |
| am-specs packs / `business.yaml` | search body = `tradingSymbols`; capture snake_case |
| am-specs OpenAPI | `InstrumentSearchCriteria.additionalProperties: false` + note |

## Live DTO proof (preprod market, dig tunnel down)

| Body field | HTTP |
|------------|------|
| `queries: ["RELIANCE"]` | **200** |
| `tradingSymbols: ["RELIANCE"]` | **200** (1 EQ hit, `trading_symbol=RELIANCE`) |
| `symbols: ["RELIANCE"]` | **400** Unrecognized field `symbols` |
| GET `/v1/fundamentals/RELIANCE` | **200** |

## Dig outage (blocked retest of all `dg_*` on dig)

After image roll, Docker Desktop/WSL failed:

`wsl.exe --unregister docker-desktop: exit status 0xffffffff`

Consequence: Kind (`am-dev-apps`) origin down → Cloudflare **1033** on `am-dev.asrax.in` (QA + market). Argo still shows `am-qa-agents-dev` Healthy with image `sha-flowvars-202611081614`, but tunnel cannot reach the cluster until Docker/WSL recovers.

**Operator recover:** fix WSL (`wsl --shutdown`, repair/reinstall `docker-desktop` distro), start Docker Desktop, confirm `kubectl --kubeconfig ~/.asrax/kubeconfig.dev get pods -n am-agents-dev`, then re-import zip + execute the 6 market flows.

## Datasets (last dig import before outage)

Re-imported via `/api/data-gen/import-zip` (profile `full`). Last sync upserted:

`dg_am-market-data_full_{search_to_fundamentals,index_quote_cluster,open_ipo_to_detail,watchlist_to_ltp,mf_detail_to_history,watchlist_create_to_items}`

Note: that import briefly lost the search step (BOM); packs are fixed locally and ready for re-import once dig is up. Include `v1/envs/dev/var_defaults.json` as payload `env` on import.

## Flow execute matrix (env=dev, last dig run before symbols/BOM fixes)

Summary then: **2 ok / 6** market (watchlist→LTP, index cluster). Search failed on `symbols` 400; IPO empty→404; watchlist create / MF upstream.

| Flow | Last dig | Expected after re-import |
|------|----------|---------------------------|
| `dg_…_watchlist_to_ltp` | ok | ok |
| `dg_…_index_quote_cluster` | ok | ok |
| `dg_…_search_to_fundamentals` | 400 `symbols` | **should pass** (tradingSymbols + capture) |
| `dg_…_open_ipo_to_detail` | 404 empty IPO | data (no open IPO) |
| `dg_…_watchlist_create_to_items` | 400 create | data/validation |
| `dg_…_mf_detail_to_history` | 500/400 | upstream/data |

## Next dig commands (when tunnel is back)

```text
1. Import: POST /api/data-gen/import-zip  service=am-market-data profile=full environment=dev activate+sync
   zip member payload.json from am-specs .generated/.../profiles/full + env from v1/envs/dev/var_defaults.json
2. GET /api/flows/dg_am-market-data_full_search_to_fundamentals → 2 nodes; body has tradingSymbols not symbols
3. Execute all 6 dg_am-market-data_full_* with credential spt-login-dev
```

## Raw artifact

`%TEMP%/md-full-payload2.zip` — fixed pack ready to import  
`%TEMP%/DIG_QA_IMAGE.txt` — last pushed dig tag
