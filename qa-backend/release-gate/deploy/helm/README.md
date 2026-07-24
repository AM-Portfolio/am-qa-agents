# qa-agent Helm

```bash
# Create secrets (do not commit values)
kubectl -n am-ai create secret generic qa-agent-gateway \
  --from-literal=QA_AGENT_GATEWAY_TOKEN='...' \
  --from-literal=GITHUB_TOKEN='' \
  --from-literal=GITHUB_WEBHOOK_SECRET='' \
  --from-literal=QA_AGENT_DATABASE_URL='' \
  --from-literal=LANGFUSE_PUBLIC_KEY='' \
  --from-literal=LANGFUSE_SECRET_KEY=''

helm upgrade --install qa-agent ./deploy/helm -n am-ai
```

Requires Temporal namespace `qa-agent` + queue `qa-agent-release-v1` and specialist Services reachable via values `env.*`.
