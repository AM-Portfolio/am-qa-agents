#!/usr/bin/env python3
"""Post a Cliq release-approval card (single admin). Does not start the workflow."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "qa-agent" / "release_gate"))
sys.path.insert(0, str(ROOT / "qa-agent"))


def main() -> int:
    from composition.env_bootstrap import load_env

    load_env()
    p = argparse.ArgumentParser(description="Request Asrax release via Cliq admin approval")
    p.add_argument("--release-id", default="")
    p.add_argument("--release-name", default="")
    p.add_argument("--env", default="prod")
    p.add_argument("--suite", default="prod_ui_full")
    p.add_argument("--url", default="https://am.asrax.in")
    p.add_argument("--soak-min", type=int, default=30)
    p.add_argument("--requested-by", default=os.getenv("USER", "") or os.getenv("USERNAME", ""))
    p.add_argument("--fixtures", action="store_true")
    p.add_argument("--skip-ui", action="store_true")
    p.add_argument("--gateway", default=os.getenv("QA_AGENT_PUBLIC_BASE_URL", "http://127.0.0.1:8150"))
    p.add_argument("--no-cliq", action="store_true", help="Create pending request without posting Cliq")
    args = p.parse_args()

    token = (os.getenv("QA_AGENT_GATEWAY_TOKEN") or "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = {
        "release_id": args.release_id or None,
        "release_name": args.release_name or None,
        "env": args.env,
        "suite": args.suite,
        "target_url": args.url,
        "soak_min": args.soak_min,
        "requested_by": args.requested_by,
        "fixtures": args.fixtures,
        "skip_ui": args.skip_ui,
        "post_cliq": not args.no_cliq,
        "use_temporal": True,
    }
    url = args.gateway.rstrip("/") + "/v2/releases/request"
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json=body, headers=headers)
    print(resp.text)
    return 0 if resp.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
