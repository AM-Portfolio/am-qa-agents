#!/usr/bin/env python3
"""Run a deterministic UI profile (in-process or via agent HTTP API)."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))


def _open_report(report: str | None) -> None:
    if not report:
        return
    path = Path(report)
    if path.is_file():
        webbrowser.open(path.resolve().as_uri())


def _resolve_target(args) -> tuple[str, str, str | None, str]:
    """Return target_url, profile, portfolio_id, login_mode."""
    target_url = args.url
    profile = args.profile
    portfolio_id = args.portfolio_id
    login_mode = args.login_mode or "demo"

    if args.target_file:
        try:
            from ui_evidence.target_loader import get_target_config
        except ImportError:
            from app.target_loader import get_target_config

        tf = Path(args.target_file).resolve()
        env_file = Path(args.env_file).resolve() if args.env_file else None
        if env_file is None:
            env_name = tf.stem.replace("targets.", "")
            candidate = tf.parent.parent / f".env.{env_name}"
            if candidate.is_file():
                env_file = candidate
        cfg = get_target_config(tf, target_name=args.target, env_file=env_file)
        target_url = target_url or cfg.base_url
        profile = profile or cfg.profile
        portfolio_id = portfolio_id or cfg.portfolio_id
        login_mode = args.login_mode or cfg.auth_login_mode
        print(
            f"Target file: {tf} module={cfg.module} env={cfg.environment} profile={profile}",
            flush=True,
        )

    if not target_url:
        target_url = "http://localhost:9000"
    if not profile:
        profile = "DASHBOARD_SMOKE_FLOW"
    return target_url, profile, portfolio_id, login_mode


async def _run_inprocess(args) -> int:
    try:
        from ui_evidence.runner import execute_ui_test
    except ImportError:
        from app.runner import execute_ui_test

    target_url, profile, portfolio_id, login_mode = _resolve_target(args)
    test_id = str(uuid.uuid4())
    payload = {
        "targetUrl": target_url,
        "specification": "",
        "profile": profile,
        "portfolioId": portfolio_id,
        "loginMode": login_mode,
        "baselineMode": args.baseline_mode,
        "designReviewEnabled": args.design_review,
        "selfHealEnabled": False,
        "viewportWidth": args.viewport_width,
        "viewportHeight": args.viewport_height,
        "branch": "local",
    }
    print(f"In-process profile={profile} url={target_url}", flush=True)
    result = await execute_ui_test(test_id, payload)
    status = result.get("status")
    print(json.dumps({k: result.get(k) for k in ("testId", "status", "error", "report", "decision", "trace")}, indent=2))
    if args.open_report:
        _open_report(result.get("report"))
    return 0 if status == "COMPLETED" else 1


def _run_http(args) -> int:
    import httpx

    target_url, profile, portfolio_id, login_mode = _resolve_target(args)
    base = args.agent_url.rstrip("/")
    payload = {
        "profile": profile,
        "targetUrl": target_url,
        "portfolioId": portfolio_id,
        "loginMode": login_mode,
        "baselineMode": args.baseline_mode,
        "designReviewEnabled": args.design_review,
        "viewportWidth": args.viewport_width,
        "viewportHeight": args.viewport_height,
    }
    print(f"POST {base}/api/v1/test/run/profile profile={profile}", flush=True)
    with httpx.Client(timeout=30.0) as client:
        try:
            resp = client.post(f"{base}/api/v1/test/run/profile", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError:
            print("ERROR: Cannot connect to ui-test-agent. Use --in-process or start the agent.", file=sys.stderr)
            return 1
        test_id = resp.json()["testId"]
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            data = client.get(f"{base}/api/v1/test/status/{test_id}").json()
            status = data.get("status")
            print(f"  status={status}", flush=True)
            if status in ("COMPLETED", "FAILED", "GO", "GO_WITH_CAVEATS", "NO_GO"):
                print(json.dumps(data, indent=2, default=str)[:2000])
                if args.open_report:
                    _open_report(data.get("report"))
                return 0 if status in ("COMPLETED", "GO", "GO_WITH_CAVEATS") else 1
            time.sleep(3)
    print("TIMEOUT", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run modern-ui domain UI flow")
    parser.add_argument("--agent-url", default="http://localhost:8130")
    parser.add_argument("--in-process", action="store_true", help="Skip HTTP; call execute_ui_test directly")
    parser.add_argument("--url", default=None)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--target-file", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--portfolio-id", default=None)
    parser.add_argument("--login-mode", choices=["demo", "credentials"], default=None)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--open-report", action="store_true")
    parser.add_argument("--baseline-mode", choices=["compare", "seed", "promote"], default=None)
    parser.add_argument("--design-review", action="store_true")
    parser.add_argument("--viewport-width", type=int, default=None)
    parser.add_argument("--viewport-height", type=int, default=None)
    args = parser.parse_args()

    if args.in_process:
        return asyncio.run(_run_inprocess(args))
    return _run_http(args)


if __name__ == "__main__":
    raise SystemExit(main())
