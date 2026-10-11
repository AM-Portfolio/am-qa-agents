"""Drive auth_user_module Temporal suite against prod; unbuffered progress for local portal."""
from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any

import httpx

BASE = "http://127.0.0.1:8150"


def main() -> int:
    rid = f"local-auth-mod-{uuid.uuid4().hex[:8]}"
    body = {
        "release_id": rid,
        "release_name": "local-auth-user-module",
        "env": "prod",
        "suite": "auth_user_module",
        "target_url": "https://am.asrax.in",
        "login_mode": "credentials",
        "soak_min": 0,
        "skip_ui": False,
        "skip_sheet": True,
        "skip_drive": True,
        "skip_cliq": True,
        "fixtures": False,
        "use_temporal": True,
        "requested_by": "auth-module-local",
    }
    with httpx.Client(base_url=BASE, timeout=180.0) as c:
        health = c.get("/health").json()
        print("HEALTH", health.get("status"), "store", health.get("db"), flush=True)
        scheme = ((health.get("db") or {}) if isinstance(health.get("db"), dict) else {}).get(
            "url_scheme"
        )
        if scheme and scheme != "sqlite":
            print("ABORT expected local sqlite ledger/runs, got", scheme, flush=True)
            return 2

        start = c.post("/v2/releases/ops/start", json=body)
        print("OPS_START", start.status_code, start.text[:500], flush=True)
        start.raise_for_status()
        started = start.json()
        req = started["request_id"]
        tid = started.get("tracking_id")
        wid = started.get("workflow_id")
        print(
            "AUTH_WF",
            "request=",
            req,
            "tracking=",
            tid,
            "workflow=",
            wid,
            "mode=",
            started.get("mode"),
            flush=True,
        )

        deadline = time.time() + 90 * 60
        last_phase = ""
        while time.time() < deadline:
            prog = c.get(f"/v2/releases/{req}").json()
            phase = prog.get("phase")
            status = prog.get("progress_status") or prog.get("status")
            if phase != last_phase:
                print(
                    "PROGRESS",
                    phase,
                    status,
                    "ui_pct=",
                    prog.get("ui_pct"),
                    "decision=",
                    prog.get("ui_decision"),
                    flush=True,
                )
                last_phase = phase
            runs = c.get("/api/runs", params={"limit": 20, "q": f"relops-{tid}"}).json()
            total = runs.get("total") if isinstance(runs, dict) else None
            print("RUNS_MATCH", total, flush=True)
            if status in {"COMPLETED", "FAILED", "completed", "failed"} or phase == "release_ops_complete":
                print("DONE", json.dumps(prog, indent=2)[:2500], flush=True)
                break
            time.sleep(15)
        else:
            print("TIMEOUT waiting for auth_user_module", flush=True)
            return 1

        final = c.get("/api/runs", params={"limit": 30, "q": f"relops-{tid}"}).json()
        print("FINAL_RUNS", json.dumps(final, indent=2)[:4000], flush=True)
        # Probe one report artifact if present
        items = (final or {}).get("runs") or (final or {}).get("items") or []
        for row in items:
            rid_run = str(row.get("id") or "")
            if not rid_run or rid_run == f"relops-{tid}":
                continue
            art = c.get(f"/api/runs/{rid_run}/artifacts")
            print("ARTIFACTS", rid_run, art.status_code, art.text[:300], flush=True)
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
