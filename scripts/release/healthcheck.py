"""GET /health against local gateway."""

from __future__ import annotations

import os
import sys

import httpx

from composition.env_bootstrap import load_env

load_env()


def main() -> int:
    port = os.getenv("QA_AGENT_PORT", "8150")
    base = os.getenv("QA_AGENT_BASE_URL", f"http://127.0.0.1:{port}")
    url = f"{base.rstrip('/')}/health"
    try:
        resp = httpx.get(url, timeout=5.0)
        print(resp.status_code, resp.text)
        return 0 if resp.status_code < 400 else 1
    except httpx.HTTPError as exc:
        print(f"health failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
