"""Local API smoke — prints working / not-working checklist. Exit 1 if critical fails."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = (os.getenv("QA_AGENT_BASE") or "http://127.0.0.1:8150").rstrip("/")

# (name, path, critical)
CHECKS: list[tuple[str, str, bool]] = [
    ("health", "/health", True),
    ("unified_health", "/unified/health", True),
    ("ready", "/ready", True),
    ("catalog", "/api/catalog", True),
    ("catalog_registrations", "/api/catalog/registrations", True),
    ("catalog_analysis_apis", "/api/catalog/am-analysis/apis?environment=dev", True),
    ("catalog_gateway_target", "/api/catalog/am-gateway/target?environment=dev", True),
    ("profiles", "/api/profiles", True),
    ("profiles_default", "/api/profiles/default", False),
    ("runs_list", "/api/runs", True),
    ("payloads", "/api/payloads", False),
    ("portal_mode", "/api/portal/mode", False),
    ("ui_test_profiles", "/api/ui-test/profiles", True),
    ("ui_v1_profiles", "/api/v1/test/profiles", True),
    ("metrics", "/metrics", False),
]


def _get(path: str) -> tuple[int, object]:
    req = urllib.request.Request(BASE + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            ctype = (resp.headers.get("content-type") or "").lower()
            if "json" in ctype:
                return resp.status, json.loads(raw.decode("utf-8", errors="replace"))
            return resp.status, raw.decode("utf-8", errors="replace")[:200]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return e.code, body
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def main() -> int:
    print(f"QA Agent smoke @ {BASE}\n")
    working: list[str] = []
    broken: list[str] = []
    critical_fail = False

    for name, path, critical in CHECKS:
        status, body = _get(path)
        ok = 200 <= status < 300
        detail = ""
        if ok and isinstance(body, dict):
            if name == "catalog" and isinstance(body.get("services"), list):
                detail = f" services={len(body['services'])}"
            elif name == "catalog_analysis_apis" and isinstance(body.get("apis"), list):
                detail = f" apis={len(body['apis'])} source={body.get('source')}"
            elif name == "profiles" and isinstance(body.get("configs"), list):
                detail = f" configs={len(body['configs'])}"
            elif name == "unified_health":
                detail = f" components={body.get('components')}"
            elif name == "health":
                detail = f" store={body.get('store')}"
            elif name == "ui_test_profiles":
                detail = f" keys={list(body)[:6]}"
        mark = "OK " if ok else "FAIL"
        print(f"  [{mark}] {name:28} HTTP {status}{detail}")
        if ok:
            working.append(name)
        else:
            broken.append(f"{name} ({status}: {body!r})" if not ok else name)
            if critical:
                critical_fail = True

    print("\n=== WORKING ===")
    for n in working:
        print(f"  - {n}")
    print("\n=== NOT WORKING ===")
    if broken:
        for n in broken:
            print(f"  - {n}")
    else:
        print("  (none)")

    print("\n=== NOTES ===")
    print("  - Qdrant cluster DNS often fails locally (UI memory bypassed) — expected")
    print("  - Temporal worker off when QA_AGENT_WORKER_ENABLED=0 — release-readiness needs Temporal")
    print("  - Portal UI: npm run ui:start (Flutter :8151 -> API :8150)")
    return 1 if critical_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
