#!/bin/sh
# Seed apps/data/dev/runtime/modules/qa from legacy apps/dev/services/am-ui-test-agent.
# Run inside vault-0 with VAULT_TOKEN set. Does not delete source path.
set -eu

SRC="${SRC_PATH:-apps/dev/services/am-ui-test-agent}"
DST="${DST_PATH:-apps/data/dev/runtime/modules/qa}"

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq required" >&2
  exit 1
fi

echo "=== path existence check ==="
for p in \
  "$SRC" \
  apps/data/dev/services/am-ui-test-agent \
  apps/data/dev/infra/observability \
  apps/dev/infra/observability \
  apps/data/dev/services/am-agents-mcp-gateway \
  apps/dev/services/am-agents-mcp-gateway \
  apps/data/dev/services/am-identity \
  apps/dev/services/am-identity
do
  if vault kv get "$p" >/dev/null 2>&1; then
    echo "OK   $p"
  else
    echo "MISS $p"
  fi
done

echo "=== source key names ($SRC) ==="
vault kv get -format=json "$SRC" > /tmp/src-qa.json
jq -r '.data.data | keys[]' /tmp/src-qa.json | sort

echo "=== copying $SRC -> $DST ==="
jq '.data.data' /tmp/src-qa.json > /tmp/qa-payload.json
vault kv put "$DST" @"/tmp/qa-payload.json"

echo "=== destination key names ($DST) ==="
vault kv get -format=json "$DST" | jq -r '.data.data | keys[]' | sort

echo "=== am-auth-policy apps/data coverage ==="
vault policy read am-auth-policy | grep -n 'apps/data' || true

echo "DONE seed $DST (source left untouched)"
rm -f /tmp/src-qa.json /tmp/qa-payload.json
