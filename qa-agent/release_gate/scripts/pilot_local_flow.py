"""Local pilot: health + CI allow (am-analysis) + CI deny (wrong service).

Default: use_temporal=true so you can track in Temporal UI.
Requires: Temporal gRPC (localhost:7233) + `npm run worker`.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

import httpx

from composition.env_bootstrap import load_env

load_env()


def _base() -> str:
    port = os.getenv("QA_AGENT_PORT", "8150")
    return os.getenv("QA_AGENT_BASE_URL", f"http://127.0.0.1:{port}").rstrip("/")


def _headers() -> dict[str, str]:
    token = os.getenv("QA_AGENT_GATEWAY_TOKEN", "dev-token-change-me")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _use_temporal() -> bool:
    return os.getenv("QA_AGENT_USE_TEMPORAL", "true").lower() in {"1", "true", "yes"}


def _temporal_ui_url(workflow_id: str) -> str:
    ui = (os.getenv("TEMPORAL_UI_EXTERNAL_URL") or "https://temporal.asrax.in").rstrip("/")
    ns = os.getenv("TEMPORAL_NAMESPACE", "qa-agent")
    return f"{ui}/namespaces/{ns}/workflows/{workflow_id}"


def _post_release(client: httpx.Client, *, service: str) -> httpx.Response:
    body = {
        "repo": os.getenv("QA_AGENT_SMOKE_REPO", "ssd2658/am-core-services"),
        "branch": os.getenv("QA_AGENT_SMOKE_BRANCH", "master"),
        "head_sha": os.getenv("QA_AGENT_SMOKE_SHA") or f"pilot{uuid.uuid4().hex[:16]}",
        "service": service,
        "ci_conclusion": "success",
        "trigger_kind": "ci_master_merge",
        "environment": os.getenv("QA_AGENT_SMOKE_ENV", "dev"),
        "assume_ci_success": True,
        "use_temporal": _use_temporal(),
    }
    return client.post(
        f"{_base()}/v2/workflows/release-readiness",
        headers=_headers(),
        json=body,
        timeout=120.0,
    )


def _poll_and_maybe_approve(client: httpx.Client, tracking_id: str, workflow_id: str) -> dict:
    """Poll ledger until HITL or terminal; auto-approve for local Temporal tracking."""
    deadline = time.time() + float(os.getenv("QA_AGENT_PILOT_POLL_SECONDS", "180"))
    last: dict = {}
    while time.time() < deadline:
        r = client.get(f"{_base()}/v2/runs/{tracking_id}", headers=_headers(), timeout=10.0)
        if r.status_code >= 400:
            time.sleep(2)
            continue
        last = r.json()
        status = str(last.get("status") or "")
        steps = last.get("steps") or {}
        print(f"  run status={status} steps={list(steps.keys())[-6:]}")
        if status in {
            "release_approved",
            "release_rejected",
            "hitl_timeout",
            "completed",
            "failed",
        }:
            return last
        needs_hitl = bool(last.get("hitl_pending")) or status in {
            "awaiting_release",
            "running",
        }
        if needs_hitl and not last.get("hitl_decision") and "awaiting_release" in steps:
            sig = client.post(
                f"{_base()}/v2/runs/{tracking_id}/signals/approve.release",
                headers=_headers(),
                json={"actor": "pilot", "notes": "local temporal pilot auto-approve"},
                timeout=30.0,
            )
            print("  approve.signal", sig.status_code, sig.text[:300])
            time.sleep(2)
            continue
        time.sleep(3)
    print(f"  still running — track in Temporal: {_temporal_ui_url(workflow_id)}")
    return last


def main() -> int:
    base = _base()
    temporal = _use_temporal()
    print(f"pilot against {base} use_temporal={temporal}")
    try:
        with httpx.Client() as client:
            health = client.get(f"{base}/health", timeout=5.0)
            print("health", health.status_code, health.text[:200])
            if health.status_code >= 400:
                return 1

            allow = _post_release(client, service="am-analysis")
            allow_data = {}
            try:
                allow_data = allow.json()
            except Exception:
                pass
            print("allow", allow.status_code)
            print(json.dumps(allow_data, indent=2)[:2500])
            if allow.status_code >= 400 or allow_data.get("skipped"):
                print("FAIL: expected allow run for am-analysis", file=sys.stderr)
                return 1

            tracking_id = str(allow_data.get("tracking_id") or "")
            workflow_id = str(allow_data.get("workflow_id") or "")
            mode = str(allow_data.get("mode") or "")
            if workflow_id:
                print(f"Temporal UI: {_temporal_ui_url(workflow_id)}")
            if mode == "inline_fallback":
                print(
                    "WARN: Temporal start failed — fell back to inline.",
                    allow_data.get("temporal_error"),
                    file=sys.stderr,
                )
            elif temporal and mode == "temporal" and tracking_id:
                print("polling run (will auto-approve at HITL)…")
                final = _poll_and_maybe_approve(client, tracking_id, workflow_id)
                print("final", json.dumps({
                    "tracking_id": final.get("tracking_id"),
                    "workflow_id": final.get("workflow_id"),
                    "status": final.get("status"),
                    "route": final.get("route"),
                    "hitl_decision": final.get("hitl_decision"),
                }, indent=2))

            deny = _post_release(client, service="am-gateway")
            deny_data = {}
            try:
                deny_data = deny.json()
            except Exception:
                pass
            print("deny", deny.status_code)
            print(json.dumps(deny_data, indent=2)[:1500])
            if not deny_data.get("skipped"):
                print("FAIL: expected skipped for am-gateway", file=sys.stderr)
                return 1
    except httpx.HTTPError as exc:
        print(f"pilot failed (is gateway up?): {exc}", file=sys.stderr)
        return 1

    print("pilot OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
