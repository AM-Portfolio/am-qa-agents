"""Bridge finished auth_user_module scenario reports into Specs Runs while suite runs."""
from __future__ import annotations

import json
import time
from pathlib import Path

from ui_evidence.bridge_specs_runs import bridge_suite_profile_run
from ui_evidence.profiles.registry import AUTH_USER_MODULE_PROFILES

REPORT_DIR = Path(__file__).resolve().parent / "data" / "reports" / "ui-test"
TID = "qa-4d0104d0b68f"
PREFIX = "a95b582f"
WID = "asrax-release-ops-local-auth-mod-a848ae4f"
RID = "local-auth-mod-a848ae4f"


def main() -> int:
    bridged: set[str] = set()
    deadline = time.time() + 25 * 60
    tick = 0
    while time.time() < deadline:
        for idx, profile in enumerate(AUTH_USER_MODULE_PROFILES):
            if profile in bridged:
                continue
            stem = f"{PREFIX}-{idx}-{profile[:16]}"
            html = REPORT_DIR / f"{stem}.html"
            jpath = REPORT_DIR / f"{stem}.json"
            if not html.is_file() and not jpath.is_file():
                continue
            status = "FAILED"
            err = None
            if jpath.is_file():
                d = json.loads(jpath.read_text(encoding="utf-8"))
                status = str(d.get("status") or status)
                err = d.get("error")
            out = bridge_suite_profile_run(
                tracking_id=TID,
                profile=profile,
                row={
                    "profile": profile,
                    "status": status,
                    "report": str(html) if html.is_file() else "",
                    "error": err,
                    "soft_failures": 0,
                },
                suite="auth_user_module",
                workflow_id=WID,
                release_id=RID,
            )
            print("bridged", profile, status, out, flush=True)
            bridged.add(profile)
        if len(bridged) >= len(AUTH_USER_MODULE_PROFILES):
            print("ALL_BRIDGED", flush=True)
            break
        tick += 1
        if tick % 3 == 0:
            print("waiting", len(bridged), "/", len(AUTH_USER_MODULE_PROFILES), flush=True)
        time.sleep(10)
    print("DONE_BRIDGE", sorted(bridged), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
