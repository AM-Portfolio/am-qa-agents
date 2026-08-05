#!/usr/bin/env python3
"""Start AsraxReleaseOpsWorkflow on Temporal (or run inline without a worker)."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_GATE = Path(__file__).resolve().parents[1] / "release_gate"
sys.path.insert(0, str(RELEASE_GATE))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _workflow_id(release_id: str | None) -> str:
    rid = release_id or f"asrax-r01-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    return f"asrax-release-ops-{rid}"


async def _async_main(args: argparse.Namespace) -> int:
    from composition.env_bootstrap import load_env

    load_env()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "tracking_id": args.tracking_id or f"qa-{uuid.uuid4().hex[:12]}",
        "release_id": args.release_id,
        "release_name": args.release_name,
        "env": args.env,
        "suite": args.suite,
        "target_url": args.url,
        "login_mode": args.login_mode,
        "portfolio_id": args.portfolio_id or os.getenv("TEST_PORTFOLIO_ID"),
        "soak_min": args.soak_min,
        "triggered_at": args.triggered_at or now,
        "workflow_started_at": now,
        "skip_ui": args.skip_ui,
        "skip_soak": args.skip_soak,
        "skip_sheet": args.skip_sheet,
        "skip_drive": args.skip_drive,
        "skip_cliq": args.skip_cliq,
        "fixtures": args.fixtures,
        "allow_unavailable_stable": args.allow_unavailable_stable,
        "sheet_id": args.sheet_id or os.getenv("ASRAX_RELEASE_SHEET_ID"),
    }

    if args.inline:
        from orchestrator.temporal_api import run_asrax_release_ops_inline

        result = await run_asrax_release_ops_inline(payload)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("complete", {}).get("status") == "COMPLETED" else 1

    from orchestrator.temporal_api import start_asrax_release_ops

    wf_id = args.workflow_id or _workflow_id(args.release_id)
    started = await start_asrax_release_ops(workflow_id=wf_id, args=payload)
    print(
        json.dumps(
            {
                "workflow_id": started,
                "hint": "Open Temporal UI → Workflows → filter AsraxReleaseOpsWorkflow; "
                "phases: init → ui_suite → pack_t0 → soak → stability_score → "
                "publish_sheet → publish_drive → cliq_final → complete",
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Start Asrax release-ops Temporal workflow")
    p.add_argument("--inline", action="store_true", help="Run activities without Temporal")
    p.add_argument("--workflow-id", default="")
    p.add_argument("--tracking-id", default="")
    p.add_argument("--release-id", default="")
    p.add_argument("--release-name", default="")
    p.add_argument("--env", default="prod")
    p.add_argument("--suite", default="prod_ui_full")
    p.add_argument("--url", default="https://am.asrax.in")
    p.add_argument("--login-mode", default="credentials")
    p.add_argument("--portfolio-id", default="")
    p.add_argument("--soak-min", type=int, default=30)
    p.add_argument("--sheet-id", default="")
    p.add_argument("--triggered-at", default="", help="ISO UTC trigger time (defaults to now)")
    p.add_argument("--skip-ui", action="store_true")
    p.add_argument("--skip-soak", action="store_true")
    p.add_argument("--skip-sheet", action="store_true")
    p.add_argument("--skip-drive", action="store_true")
    p.add_argument("--skip-cliq", action="store_true")
    p.add_argument("--fixtures", action="store_true")
    p.add_argument("--allow-unavailable-stable", action="store_true")
    return asyncio.run(_async_main(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
