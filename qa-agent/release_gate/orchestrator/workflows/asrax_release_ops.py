"""AsraxReleaseOpsWorkflow — T0 UI pack → soak → score → Sheet/Drive/Cliq.

Designed for Temporal UI tracing: each phase logs flow.phase=... and each
activity has a stable name (activity_release_ops_*).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestrator.activities.release_ops import (
        activity_release_ops_cliq_final,
        activity_release_ops_complete,
        activity_release_ops_init,
        activity_release_ops_pack_t0,
        activity_release_ops_publish_drive,
        activity_release_ops_publish_sheet,
        activity_release_ops_stability_score,
        activity_release_ops_ui_suite,
        activity_release_ops_wait_deploy_healthy,
    )


@workflow.defn(name="AsraxReleaseOpsWorkflow")
class AsraxReleaseOpsWorkflow:
    """End-to-end Asrax release evidence + final stability broadcast."""

    @workflow.run
    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        retry = RetryPolicy(maximum_attempts=3)
        short = timedelta(minutes=20)
        long_ui = timedelta(minutes=90)
        wf_id = workflow.info().workflow_id
        soak_min = int(args.get("soak_min") or 30)

        def _phase(phase: str, detail: str = "") -> None:
            msg = f"flow.phase={phase} workflow_id={wf_id} domain=release_ops"
            if detail:
                msg += f" {detail}"
            workflow.logger.info(msg)

        _phase("init")
        init = await workflow.execute_activity(
            activity_release_ops_init,
            {**args, "workflow_id": wf_id},
            start_to_close_timeout=short,
            retry_policy=retry,
        )
        tracking_id = init["tracking_id"]
        release_id = init["release_id"]
        pack_path = init["pack_path"]
        _phase("init", f"release_id={release_id} tracking_id={tracking_id}")

        _phase("wait_deploy_healthy")
        first = await workflow.execute_activity(
            activity_release_ops_wait_deploy_healthy,
            {
                "tracking_id": tracking_id,
                "pack_path": pack_path,
                "target_url": args.get("target_url") or args.get("url"),
                "ui_test_base": args.get("ui_test_base"),
                "qa_base": args.get("qa_base"),
                "fixtures": bool(args.get("fixtures")),
                "skip_wait_healthy": bool(args.get("skip_wait_healthy")),
            },
            start_to_close_timeout=short,
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        _phase("wait_deploy_healthy", f"ok={first.get('ok')} pending={first.get('pending')}")

        _phase("ui_suite")
        ui = await workflow.execute_activity(
            activity_release_ops_ui_suite,
            {
                "tracking_id": tracking_id,
                "release_id": release_id,
                "pack_path": pack_path,
                "suite": args.get("suite") or "prod_ui_full",
                "target_url": args.get("target_url") or args.get("url"),
                "login_mode": args.get("login_mode") or "credentials",
                "portfolio_id": args.get("portfolio_id"),
                "skip_ui": bool(args.get("skip_ui")),
            },
            start_to_close_timeout=long_ui,
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        _phase("ui_suite", f"decision={ui.get('decision')}")

        _phase("pack_t0")
        pack_t0 = await workflow.execute_activity(
            activity_release_ops_pack_t0,
            {
                "tracking_id": tracking_id,
                "release_id": release_id,
                "pack_path": pack_path,
                "skip_sheet": bool(args.get("skip_sheet")),
                "sheet_id": args.get("sheet_id"),
            },
            start_to_close_timeout=short,
            retry_policy=retry,
        )
        _phase("pack_t0", "done")

        if soak_min > 0 and not args.get("skip_soak"):
            _phase("soak", f"minutes={soak_min}")
            await workflow.sleep(timedelta(minutes=soak_min))
            _phase("soak", "elapsed")
        else:
            _phase("soak", "skipped")

        _phase("stability_score")
        stability = await workflow.execute_activity(
            activity_release_ops_stability_score,
            {
                "tracking_id": tracking_id,
                "release_id": release_id,
                "pack_path": pack_path,
                "soak_min": soak_min,
                "fixtures": bool(args.get("fixtures")),
                "allow_unavailable_stable": bool(args.get("allow_unavailable_stable")),
            },
            start_to_close_timeout=short,
            retry_policy=retry,
        )
        _phase("stability_score", f"band={stability.get('band')} score={stability.get('stability_score')}")

        _phase("publish_sheet")
        sheet = await workflow.execute_activity(
            activity_release_ops_publish_sheet,
            {
                "tracking_id": tracking_id,
                "stability": stability,
                "skip_sheet": bool(args.get("skip_sheet")),
                "sheet_id": args.get("sheet_id"),
            },
            start_to_close_timeout=short,
            retry_policy=retry,
        )
        _phase("publish_sheet", f"ok={sheet.get('ok')} skipped={sheet.get('skipped')}")

        _phase("publish_drive")
        drive = await workflow.execute_activity(
            activity_release_ops_publish_drive,
            {
                "tracking_id": tracking_id,
                "release_id": release_id,
                "pack_path": pack_path,
                "skip_drive": bool(args.get("skip_drive")),
            },
            start_to_close_timeout=short,
            retry_policy=retry,
        )
        _phase("publish_drive", f"ok={drive.get('ok')} skipped={drive.get('skipped')}")

        _phase("cliq_final")
        cliq = await workflow.execute_activity(
            activity_release_ops_cliq_final,
            {
                "tracking_id": tracking_id,
                "release_id": release_id,
                "release_name": args.get("release_name") or release_id,
                "pack_path": pack_path,
                "stability": stability,
                "drive": drive,
                "ui": ui,
                "skip_cliq": bool(args.get("skip_cliq")),
            },
            start_to_close_timeout=short,
            retry_policy=retry,
        )
        _phase("cliq_final", f"ok={cliq.get('ok')} skipped={cliq.get('skipped')}")

        _phase("complete")
        complete = await workflow.execute_activity(
            activity_release_ops_complete,
            {
                "tracking_id": tracking_id,
                "release_id": release_id,
                "pack_path": pack_path,
                "stability": stability,
            },
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry,
        )
        _phase("complete", f"band={complete.get('band')}")

        return {
            "tracking_id": tracking_id,
            "release_id": release_id,
            "workflow_id": wf_id,
            "pack_path": pack_path,
            "ui": ui,
            "pack_t0": pack_t0,
            "stability": stability,
            "sheet": sheet,
            "drive": drive,
            "cliq": {k: v for k, v in cliq.items() if k != "body"},
            "complete": complete,
            "system_stable": bool(stability.get("system_stable")),
        }
