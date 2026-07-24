"""Smoke: POST release-readiness (inline) and print outcome summary."""

from __future__ import annotations

import json
import os
import sys

import httpx

from am_qa_agent.env_bootstrap import load_env

load_env()


def main() -> int:
    port = os.getenv("QA_AGENT_PORT", "8150")
    base = os.getenv("QA_AGENT_BASE_URL", f"http://127.0.0.1:{port}").rstrip("/")
    token = os.getenv("QA_AGENT_GATEWAY_TOKEN", "dev-token-change-me")
    body = {
        "repo": os.getenv("QA_AGENT_SMOKE_REPO", "ssd2658/am-core-services"),
        "branch": os.getenv("QA_AGENT_SMOKE_BRANCH", "master"),
        "head_sha": os.getenv("QA_AGENT_SMOKE_SHA", "abc123def4567890"),
        "ci_conclusion": "success",
        "trigger_kind": os.getenv("QA_AGENT_SMOKE_TRIGGER", "manual"),
        "environment": os.getenv("QA_AGENT_SMOKE_ENV", "dev"),
        "use_temporal": os.getenv("QA_AGENT_USE_TEMPORAL", "true").lower()
        in {"1", "true", "yes"},
    }
    service = (os.getenv("QA_AGENT_SMOKE_SERVICE") or "").strip()
    if service:
        body["service"] = service
    elif body["trigger_kind"] == "ci_master_merge":
        body["service"] = "am-analysis"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{base}/v2/workflows/release-readiness"
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=120.0)
    except httpx.HTTPError as exc:
        print(f"smoke failed (is gateway up?): {exc}", file=sys.stderr)
        return 1
    print(resp.status_code)
    try:
        data = resp.json()
    except Exception:
        print(resp.text)
        return 1 if resp.status_code >= 400 else 0
    print(json.dumps(data, indent=2)[:4000])
    outcome = data.get("outcome") or {}
    tracking = data.get("tracking_id") or outcome.get("tracking_id")
    print(f"\ntracking_id={tracking} status={outcome.get('status') or data.get('status')}")
    return 0 if resp.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
