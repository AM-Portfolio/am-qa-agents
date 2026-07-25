"""Poll release-readiness run until terminal status."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request

POD = "am-qa-agents-ddb6c8dcd-bwdcx"
NS = "am-apps-dev"
BASE = "http://127.0.0.1:18150"
TRACKING = sys.argv[1] if len(sys.argv) > 1 else "qa-6c151027c16a"
MAX_WAIT = int(sys.argv[2]) if len(sys.argv) > 2 else 2400  # 40 min


def vault_token() -> str:
    raw = subprocess.check_output(
        ["kubectl", "exec", "-n", NS, POD, "-c", "am-qa-agents", "--", "cat", "/vault/secrets/qa-agent"],
        text=True,
    )
    m = re.search(r"(?:^|\n)(?:export\s+)?QA_AGENT_GATEWAY_TOKEN=(.+)", raw)
    if not m:
        raise SystemExit("token missing")
    return m.group(1).strip().strip('"').strip("'")


def fetch(token: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/v2/runs/{TRACKING}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main() -> int:
    token = vault_token()
    terminal = {"completed", "failed", "cancelled", "timed_out", "awaiting_hitl", "done", "error"}
    t0 = time.time()
    last = ""
    while time.time() - t0 < MAX_WAIT:
        try:
            data = fetch(token)
        except Exception as exc:  # noqa: BLE001
            print(f"poll_error={exc}", flush=True)
            time.sleep(10)
            continue
        status = str(data.get("status") or data.get("outcome", {}).get("status") or "?")
        line = json.dumps(
            {
                "elapsed_s": int(time.time() - t0),
                "status": status,
                "releasable": (data.get("outcome") or data).get("releasable"),
                "recommendation": (data.get("outcome") or data).get("recommendation"),
                "keys": sorted(data.keys())[:20],
            }
        )
        if line != last:
            print(line, flush=True)
            last = line
        # dump fuller snapshot every ~2 min
        if int(time.time() - t0) % 120 < 8:
            print("SNAPSHOT=" + json.dumps(data)[:2500], flush=True)
        st = status.lower()
        if st in terminal or "complete" in st or "fail" in st:
            print("FINAL=" + json.dumps(data, indent=2)[:8000], flush=True)
            return 0
        time.sleep(8)
    print("TIMEOUT_WAITING", flush=True)
    try:
        print("LAST=" + json.dumps(fetch(token), indent=2)[:8000])
    except Exception as exc:  # noqa: BLE001
        print(exc)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
