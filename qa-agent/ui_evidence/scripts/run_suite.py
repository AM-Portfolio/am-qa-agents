#!/usr/bin/env python3
"""Run smoke / release_gate / prod_ui_full suite sequentially (in-process)."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Prefer package root (qa-agent parent) so `ui_evidence` imports resolve.
sys.path.insert(0, str(ROOT.parent))


async def main_async(args) -> int:
    try:
        from ui_evidence.config import settings
        from ui_evidence.profiles.registry import suite_profiles
        from ui_evidence.runner import execute_ui_test
    except ImportError:
        from app.config import settings
        from app.profiles.registry import suite_profiles
        from app.runner import execute_ui_test

    target_url = args.url or settings.MODERN_UI_MAIN_URL
    if args.target_file:
        try:
            from ui_evidence.target_loader import get_target_config
        except ImportError:
            from app.target_loader import get_target_config

        cfg = get_target_config(
            Path(args.target_file).resolve(),
            target_name=args.target or "release_gate",
            env_file=Path(args.env_file).resolve() if args.env_file else None,
        )
        target_url = args.url or cfg.base_url

    profiles = list(suite_profiles(args.suite))
    login_mode = args.login_mode
    if args.suite == "prod_ui_full" and login_mode == "demo":
        login_mode = "credentials"

    suite_id = str(uuid.uuid4())
    results = []
    hard = soft = 0
    print(
        f"Suite {args.suite} id={suite_id} target={target_url} login={login_mode}",
        flush=True,
    )

    for i, profile in enumerate(profiles):
        child_id = f"{suite_id[:8]}-{i}-{profile[:16]}"
        payload = {
            "targetUrl": target_url,
            "specification": "",
            "profile": profile,
            "portfolioId": args.portfolio_id or settings.TEST_PORTFOLIO_ID,
            "loginMode": login_mode,
            "designReviewEnabled": bool(args.design_review and i == len(profiles) - 1),
            "selfHealEnabled": False,
            "branch": "suite",
        }
        print(f"\n=== [{i + 1}/{len(profiles)}] {profile} ===", flush=True)
        result = await execute_ui_test(child_id, payload)
        status = result.get("status")
        print(f"  -> {status} report={result.get('report')}", flush=True)
        if status == "FAILED":
            hard += 1
        if result.get("soft_failures"):
            soft += 1
        results.append(
            {
                "profile": profile,
                "status": status,
                "error": result.get("error"),
                "report": result.get("report"),
                "duration_ms": result.get("duration_ms"),
                "soft_failures": len(result.get("soft_failures") or []),
            }
        )

    if hard:
        decision = "NO_GO"
        code = 1
    elif soft:
        decision = "GO_WITH_CAVEATS"
        code = 0
    else:
        decision = "GO"
        code = 0

    summary = {
        "suiteId": suite_id,
        "suite": args.suite,
        "decision": decision,
        "targetUrl": target_url,
        "loginMode": login_mode,
        "hard_fail_count": hard,
        "soft_fail_count": soft,
        "results": results,
    }
    out_dir = Path(settings.REPORT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"suite-{suite_id}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n=== {decision} ===\nSummary: {out_path}", flush=True)
    print(json.dumps(summary, indent=2))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="UI smoke / release_gate / prod_ui_full suite")
    parser.add_argument(
        "--suite",
        choices=["release_gate", "smoke", "prod_ui_full"],
        default="release_gate",
    )
    parser.add_argument("--url", default=None)
    parser.add_argument("--target-file", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--portfolio-id", default=None)
    parser.add_argument("--login-mode", choices=["demo", "credentials"], default="demo")
    parser.add_argument("--design-review", action="store_true")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
