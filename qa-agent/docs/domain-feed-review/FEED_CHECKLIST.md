# Feed checklist (dev → preprod → prod)

Control plane: local qa-agent `http://127.0.0.1:8150`  
Contracts: `am-specs/services/<id>/openapi.*`  
Registrations: `qa-agent/catalog-external/<id>/spt.yaml`

## Prereq

```powershell
$env:SPT_CATALOG_EXTERNAL = "F:\am-repos\am-repos\am-qa-agents\qa-agent\catalog-external"
# restart composition.main if agent started without this env
```

## Automate

```powershell
cd F:\am-repos\am-repos\am-qa-agents\qa-agent\docs\domain-feed-review
python _seed_spts_and_openapi.py
python _upsert_authored_flows.py
```

## Manual per env (if needed)

For each service in `catalog.yaml` and env in `dev|preprod|prod`:

1. Seed OpenAPI: `POST /api/catalog/{id}/openapi/seed?environment={env}&from_payload_set=false` with document from am-specs  
2. Overview: `GET /api/services/{id}/overview?environment={env}`  
3. Portal: set environment dropdown → Services / OpenAPI / Flows  

## Prod gate

- Do **not** run dev-only mutating flows (OMS create/cancel, watchlist create, parser upload) on prod  
- Prefer health / plans / list / replay reads  

## Review artifacts

- [catalog.yaml](catalog.yaml)  
- [services/](services/)  
- [FLOWS_REVIEW.md](FLOWS_REVIEW.md)  
- [cross_domain_flows.yaml](cross_domain_flows.yaml)  
- [SEED_REPORT.json](SEED_REPORT.json) (after seed)  
