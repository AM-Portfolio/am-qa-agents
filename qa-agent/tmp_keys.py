import json
import subprocess

pod = subprocess.check_output(
    [
        "kubectl",
        "get",
        "pods",
        "-n",
        "am-apps-dev",
        "-l",
        "app.kubernetes.io/instance=am-qa-agents",
        "-o",
        "jsonpath={.items[0].metadata.name}",
    ],
    text=True,
).strip()
raw = subprocess.check_output(
    [
        "kubectl",
        "exec",
        "-n",
        "am-apps-dev",
        pod,
        "-c",
        "vault-agent",
        "--",
        "sh",
        "-c",
        "export VAULT_ADDR=http://vault.vault.svc:8200; "
        "export VAULT_TOKEN=$(cat /home/vault/.vault-token); "
        "vault kv get -format=json apps/data/dev/runtime/modules/qa",
    ],
    text=True,
    errors="replace",
)
data = json.loads(raw[raw.find("{") :])["data"]["data"]
for k in sorted(data):
    print(repr(k))
