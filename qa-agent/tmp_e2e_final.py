import json
import time
import urllib.request
import uuid
from pathlib import Path


def load_vault():
    env = {}
    for ln in Path("/vault/secrets/qa-agent").read_text().splitlines():
        ln = ln.strip()
        if ln.startswith("export "):
            ln = ln[len("export ") :]
        if "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


vault = load_vault()
token = vault.get("QA_AGENT_GATEWAY_TOKEN") or ""
reg = json.load(
    urllib.request.urlopen("http://127.0.0.1:8150/api/catalog/registrations", timeout=20)
)
print("catalog_count", reg.get("count"), [s.get("id") for s in (reg.get("services") or [])])

sha = "e2e" + uuid.uuid4().hex[:37]
payload = {
    "repo": "AM-Portfolio/am-core-services",
    "branch": "master",
    "head_sha": sha,
    "service": "am-analysis",
    "ci_conclusion": "success",
    "trigger_kind": "ci_master_merge",
    "environment": "dev",
    "assume_ci_success": True,
    "use_temporal": True,
    "target_url": "https://am-dev.asrax.in",
}
body = json.dumps(payload).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8150/v2/workflows/release-readiness",
    data=body,
    method="POST",
    headers={
        "Content-Type": "application/json",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    },
)
try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode()
        code = resp.status
except Exception as e:
    raw = e.read().decode() if hasattr(e, "read") else str(e)
    code = getattr(e, "code", 0)
print("POST_HTTP", code)
data = json.loads(raw)
print("mode", data.get("mode"), "wf", data.get("workflow_id"), "terr", data.get("temporal_error"))
tid = data.get("tracking_id")
print("TRACKING_ID", tid)
if not tid:
    print(raw[:2000])
    raise SystemExit(2)

# If inline outcome already present, print verify from it
if data.get("mode") in {"inline", "inline_fallback"} and isinstance(data.get("outcome"), dict):
    outcome = data["outcome"]
    # still poll ledger for normalized steps
    pass

deadline = time.time() + 1800
last = None
run = {}
steps = {}
while time.time() < deadline:
    r = urllib.request.Request(
        f"http://127.0.0.1:8150/v2/runs/{tid}",
        headers={**({"Authorization": f"Bearer {token}"} if token else {})},
    )
    with urllib.request.urlopen(r, timeout=30) as resp:
        run = json.loads(resp.read().decode())
    status = run.get("status")
    steps = run.get("steps") or {}
    verify = steps.get("post_test_verify") or {}
    mx = steps.get("execute_matrix") or {}
    summary = {
        "status": status,
        "releasable": verify.get("releasable"),
        "blockers": verify.get("blockers"),
        "ui": mx.get("ui_status"),
        "api": mx.get("api_status"),
        "spt": mx.get("spt_specs_status"),
        "catalog": (steps.get("ensure_catalog_ready") or {}).get("ready"),
        "steps": sorted(steps.keys()),
    }
    line = json.dumps(summary, default=str)
    if line != last:
        print("POLL", line)
        last = line
    if status in {
        "failed",
        "rejected",
        "completed",
        "approved",
        "blocked_gnx_down",
        "error",
        "hitl_timeout",
    }:
        break
    if verify.get("releasable") is not None or "awaiting_release" in steps:
        break
    time.sleep(15)

verify = steps.get("post_test_verify") or {}
print("FINAL")
print(
    json.dumps(
        {
            "tracking_id": tid,
            "status": run.get("status"),
            "releasable": verify.get("releasable"),
            "blockers": verify.get("blockers"),
            "ensure_catalog_ready": steps.get("ensure_catalog_ready"),
            "execute_matrix": steps.get("execute_matrix"),
            "awaiting_release": steps.get("awaiting_release"),
            "analyze": {
                k: (steps.get("analyze_release") or {}).get(k)
                for k in ("recommendation", "executive_summary")
            },
            "publication": {
                k: (steps.get("publish_pdf") or steps.get("publication") or {}).get(k)
                for k in ("pdf_written", "pdf_docs_ref")
            },
        },
        default=str,
    )
)
releasable = verify.get("releasable")
print("GO_NO_GO", "GO" if releasable is True else "NO-GO")
