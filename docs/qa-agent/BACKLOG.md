# Remaining backlog — what still needs *environment* (not code)

Code scaffolds for former “pending” items are now in-repo. These still need real cluster/credentials:

| Item | Code location | Needs from you |
|------|---------------|----------------|
| Helm deploy | `deploy/helm/` | `kubectl` + secret `qa-agent-gateway` |
| Temporal cluster | worker Helm + `TEMPORAL_HOST` | Temporal namespace + queue `qa-agent-v1` |
| GitHub App | `deploy/github-app.md` | Create App; set webhook + secrets |
| Langfuse live LLM | `intelligence/llm.py` | `LANGFUSE_*` + `OPENAI_API_KEY` |
| MinIO PDF | `adapters/document_store.py` | `QA_AGENT_PDF_STORE=document.store` + tool-agent |
| Live Grafana | `observe.py` + `config/grafana-catalog.yaml` | tool-agent observe + Prom |
| Postgres | sqlite default; `QA_AGENT_DATABASE_URL` reserved | Optional migrate later |
| GrowthBook | `adapters/growthbook.py` | API host/key; unset `QA_AGENT_SKIP_GROWTHBOOK` |
| Semgrep/CodeQL | SAST heuristics only | Wire CI conclusions into hook |
| DAST | `run_dast_hook` stub | `QA_AGENT_DAST_ENABLED=true` + scanner |
| HITL Cliq UI | API signals only | Cliq card → gateway signal |
| weasyprint PDF | optional extra `[pdf]` | `pip install -e ".[pdf]"` |

Local durable store: `QA_AGENT_STORE=sqlite` + `QA_AGENT_SQLITE_PATH=...`
