"""One-shot: extract gateway token from pod vault file and start release-readiness."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

POD = "am-qa-agents-ddb6c8dcd-bwdcx"
NS = "am-apps-dev"
BASE = "http://127.0.0.1:18150"


def vault_token() -> str:
    raw = subprocess.check_output(
        ["kubectl", "exec", "-n", NS, POD, "-c", "am-qa-agents", "--", "cat", "/vault/secrets/qa-agent"],
        text=True,
    )
    m = re.search(r"(?:^|\n)(?:export\s+)?QA_AGENT_GATEWAY_TOKEN=(.+)", raw)
    if not m:
        raise SystemExit("QA_AGENT_GATEWAY_TOKEN not found in vault secrets")
    return m.group(1).strip().strip('"').strip("'")


def main() -> int:
    token = vault_token()
    body = {
        "repo": "ssd2658/am-core-services",
        "branch": "master",
        "head_sha": "623b49995802819afcf5442d17e2b90192c2f1de",
        "ci_conclusion": "success",
        "trigger_kind": "manual",
        "environment": "dev",
        "service": "am-analysis",
        "profile": "RELEASE_GATE",
        "assume_ci_success": True,
        "use_temporal": True,
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/v2/workflows/release-readiness",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            payload = r.read().decode()
            print(r.status)
            print(payload[:6000])
            return 0
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode()[:3000], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
