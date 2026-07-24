"""Run the full UI test graph locally (Playwright → optional design review → report)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.agent.graph import test_agent_graph
from app.browser.controller import browser_controller
from app.config import settings
from app.context import TestRunContext
from app.llm.factory import create_llm_client

logger = logging.getLogger(__name__)


async def execute_ui_test(test_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Execute plan → execute → assert → design_review → report.

    Returns result dict with keys: status, report, error, design_review, sessionId, ...
    """
    session_id = f"ui-test-{test_id[:8]}"
    llm_client = create_llm_client()
    baseline_mode = (payload.get("baselineMode") or settings.BASELINE_MODE).lower()
    target_url = payload["targetUrl"]
    profile = payload["profile"]

    # Per-run overrides for release gate
    design_override = payload.get("designReviewEnabled")
    heal_override = payload.get("selfHealEnabled")
    prev_design = settings.DESIGN_REVIEW_ENABLED
    prev_heal = settings.SELF_HEAL_ENABLED
    if design_override is not None:
        settings.DESIGN_REVIEW_ENABLED = bool(design_override)
    if heal_override is not None:
        settings.SELF_HEAL_ENABLED = bool(heal_override)

    ctx = TestRunContext(
        test_id=test_id,
        session_id=session_id,
        profile=profile,
        llm_client=llm_client,
        commit_sha=payload.get("commitSha"),
        branch=payload.get("branch", "main"),
        baseline_mode=baseline_mode,
        base_url=target_url,
        step_retry_count=int(
            payload.get("stepRetryCount", settings.STEP_RETRY_COUNT) or 0
        ),
    )
    ctx.mark_run_start()

    out: dict[str, Any] = {
        "testId": test_id,
        "status": "RUNNING",
        "sessionId": session_id,
        "baseline_mode": baseline_mode,
        "profile": profile,
    }

    vw = int(payload.get("viewportWidth") or settings.BROWSER_VIEWPORT_WIDTH)
    vh = int(payload.get("viewportHeight") or settings.BROWSER_VIEWPORT_HEIGHT)
    trace_dir = Path(settings.REPORT_DIR) / "traces" / test_id
    save_trace_ref: list[bool] = [False]

    try:
        await browser_controller.start(headless=settings.HEADLESS)
        async with browser_controller.get_page(
            viewport_width=vw,
            viewport_height=vh,
            trace_dir=trace_dir,
            trace_mode=settings.PLAYWRIGHT_TRACE,
            console_sink=ctx.console_errors,
            save_trace_ref=save_trace_ref,
        ) as (page, trace_path):
            ctx.page = page
            ctx.trace_path = str(trace_path) if trace_path else None
            initial_state: dict[str, Any] = {
                "target_url": target_url,
                "specification": payload.get("specification") or "",
                "steps": [],
                "current_step_index": 0,
                "selectors_db": {},
                "failures_encountered": [],
                "soft_failures": [],
                "screenshot_history": [],
                "screenshot_labels": [],
                "report_output": None,
                "mongodb_report_id": None,
                "testing_goal": f"Execute {profile} for branch {payload.get('branch')}",
                "git_diff": None,
                "visited_routes": [],
                "action_log": [],
                "visual_anomalies": [],
                "design_review_results": [],
                "design_review_summary": {},
                "baseline_mode": baseline_mode,
            }
            portfolio_id = payload.get("portfolioId") or settings.TEST_PORTFOLIO_ID
            prev_pf = settings.TEST_PORTFOLIO_ID
            if portfolio_id:
                settings.TEST_PORTFOLIO_ID = portfolio_id
            login_mode = payload.get("loginMode") or settings.AUTH_LOGIN_MODE
            prev_login = settings.AUTH_LOGIN_MODE
            if payload.get("loginMode"):
                settings.AUTH_LOGIN_MODE = login_mode
            try:
                result = await test_agent_graph.ainvoke(
                    initial_state,
                    config={"configurable": {"test_context": ctx}},
                )
            finally:
                settings.TEST_PORTFOLIO_ID = prev_pf
                settings.AUTH_LOGIN_MODE = prev_login

            soft = result.get("soft_failures") or []
            hard = result.get("failures_encountered") or []
            if hard:
                save_trace_ref[0] = True
            out["status"] = "COMPLETED" if not hard else "FAILED"
            out["report"] = result.get("report_output")
            out["action_log"] = ctx.action_log
            out["duration_ms"] = ctx.total_duration_ms()
            out["step_timings"] = ctx.step_timings
            out["design_review"] = result.get("design_review_summary")
            out["soft_failures"] = soft
            out["failures"] = hard
            out["console_errors"] = ctx.console_errors
            if hard:
                out["error"] = hard[-1].get("error") or "assertion/step failed"
            logger.info("UI test %s completed — report %s", test_id, result.get("report_output"))
            return out
    except Exception as exc:
        save_trace_ref[0] = True
        logger.error("UI test %s failed: %s", test_id, exc)
        out["status"] = "FAILED"
        out["error"] = str(exc)
        out["action_log"] = ctx.action_log
        out["duration_ms"] = ctx.total_duration_ms()
        out["step_timings"] = ctx.step_timings
        out["console_errors"] = ctx.console_errors
        report_guess = Path(settings.REPORT_DIR) / f"{test_id}.html"
        if report_guess.is_file():
            out["report"] = str(report_guess)
        return out
    finally:
        if ctx.trace_path and Path(ctx.trace_path).is_file():
            out["trace"] = ctx.trace_path
        settings.DESIGN_REVIEW_ENABLED = prev_design
        settings.SELF_HEAL_ENABLED = prev_heal
        await browser_controller.stop()
