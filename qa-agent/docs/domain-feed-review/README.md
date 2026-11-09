# Domain feed review pack

Reviewable **Catalog / Services / Flows** for market, portfolio, trade, analysis, parser, news, subscription across **dev / preprod / prod** (am-specs targets).

| File | What |
|------|------|
| [catalog.yaml](catalog.yaml) | Service ids + env URLs + OpenAPI ops |
| [services/](services/) | Per-service review cards |
| [FLOWS_REVIEW.md](FLOWS_REVIEW.md) | Flow inventory + env gates |
| [cross_domain_flows.yaml](cross_domain_flows.yaml) | First-feed cross-domain journeys |
| [FEED_CHECKLIST.md](FEED_CHECKLIST.md) | How to re-seed / verify |
| [SEED_REPORT.json](SEED_REPORT.json) | Last OpenAPI seed + overview HTTP codes |
| [AUTHORED_FLOWS_REPORT.json](AUTHORED_FLOWS_REPORT.json) | Flows upserted into local qa-agent |

Helpers (optional): `_extract_catalog.py`, `_gen_service_cards.py`, `_seed_spts_and_openapi.py`, `_upsert_authored_flows.py`.

Portal: `npm run run:windows` → switch environment dev/preprod/prod → Services / OpenAPI / Flows.
