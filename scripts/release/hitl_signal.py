"""Send HITL approve.release / reject.release. Usage: python scripts/hitl_signal.py approve [tracking_id]"""

from __future__ import annotations

import json
import os
import sys

import httpx

from composition.env_bootstrap import load_env

load_env()


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"approve", "reject"}:
        print("usage: python scripts/hitl_signal.py approve|reject [tracking_id]", file=sys.stderr)
        return 2
    action = sys.argv[1]
    tracking_id = sys.argv[2] if len(sys.argv) > 2 else os.getenv("QA_AGENT_TRACKING_ID", "")
    if not tracking_id:
        print("tracking_id required (arg or QA_AGENT_TRACKING_ID)", file=sys.stderr)
        return 2
    signal = "approve.release" if action == "approve" else "reject.release"
    port = os.getenv("QA_AGENT_PORT", "8150")
    base = os.getenv("QA_AGENT_BASE_URL", f"http://127.0.0.1:{port}").rstrip("/")
    token = os.getenv("QA_AGENT_GATEWAY_TOKEN", "dev-token-change-me")
    url = f"{base}/v2/runs/{tracking_id}/signals/{signal}"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"actor": os.getenv("QA_AGENT_HITL_ACTOR", "operator"), "notes": action},
        timeout=30.0,
    )
    print(resp.status_code)
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)
    return 0 if resp.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
