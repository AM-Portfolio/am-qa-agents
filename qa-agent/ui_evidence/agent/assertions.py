from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from ui_evidence.agent.state import AutonomousAgentState
from ui_evidence.context import get_test_context

logger = logging.getLogger(__name__)


def _fail(state, idx, step, error: str, ctx, duration_ms: float) -> dict:
    failures = list(state.get("failures_encountered") or [])
    failures.append(
        {
            "type": "assertion_failed",
            "step_index": idx,
            "step": step,
            "error": error,
        }
    )
    ctx.record_step_timing(
        index=idx,
        name=step.get("name", step.get("action", "")),
        action=step.get("action", ""),
        phase="assert",
        duration_ms=duration_ms,
        status="failed",
        error=error,
    )
    ctx.log_action("assert_failed", step=step.get("name"), error=error, duration_ms=duration_ms)
    out = {"failures_encountered": failures}
    if state.get("soft_failures"):
        out["soft_failures"] = state["soft_failures"]
    return out


def _soft_fail(state, idx, step, error: str, ctx, duration_ms: float) -> dict:
    """Record warning without failing the run."""
    warnings = list(state.get("soft_failures") or [])
    warnings.append(
        {
            "type": "assertion_soft_failed",
            "step_index": idx,
            "step": step,
            "error": error,
        }
    )
    ctx.record_step_timing(
        index=idx,
        name=step.get("name", step.get("action", "")),
        action=step.get("action", ""),
        phase="assert",
        duration_ms=duration_ms,
        status="warn",
        error=error,
    )
    ctx.log_action("assert_soft_fail", step=step.get("name"), error=error, duration_ms=duration_ms)
    logger.warning("[%s] SOFT FAIL: %s", step.get("name"), error)
    return {"soft_failures": warnings}


async def assert_node(state: AutonomousAgentState, config: RunnableConfig) -> dict[str, Any]:
    ctx = get_test_context(config)
    page = ctx.page
    if page is None:
        raise RuntimeError("Playwright page not initialized")

    idx = max(0, state.get("current_step_index", 1) - 1)
    steps = state.get("steps") or []
    if idx >= len(steps):
        return {}

    step = steps[idx]
    action = step.get("action")
    name = step.get("name", action)
    soft = bool(step.get("soft"))
    t0 = time.perf_counter()

    def on_fail(error: str) -> dict:
        duration_ms = (time.perf_counter() - t0) * 1000
        if soft:
            return _soft_fail(state, idx, step, error, ctx, duration_ms)
        return _fail(state, idx, step, error, ctx, duration_ms)

    if action == "assert_title_not_empty":
        title = await page.title()
        duration_ms = (time.perf_counter() - t0) * 1000
        if not title or not title.strip():
            return on_fail("Page title is empty")
        ctx.record_step_timing(
            index=idx, name=name, action=action, phase="assert", duration_ms=duration_ms, status="ok"
        )
        ctx.log_action("assert_pass", step=name, title=title, duration_ms=duration_ms)
        logger.info("[%s] PASS title=%r", name, title)

    elif action == "assert_url_contains":
        pattern = step["pattern"]
        current = page.url
        duration_ms = (time.perf_counter() - t0) * 1000
        if pattern not in current:
            return on_fail(f"URL {current!r} does not contain {pattern!r}")
        ctx.record_step_timing(
            index=idx, name=name, action=action, phase="assert", duration_ms=duration_ms, status="ok"
        )
        ctx.log_action("assert_pass", step=name, url=current, duration_ms=duration_ms)
        logger.info("[%s] PASS url=%s", name, current)

    elif action == "assert_text_visible":
        texts = step.get("texts") or [step.get("text", "")]
        timeout = int(step.get("timeout_ms", 20000))
        # soft with multiple texts: pass if ANY text visible
        if soft and len([t for t in texts if t]) > 1:
            found = False
            last_err = ""
            for text in texts:
                if not text:
                    continue
                try:
                    await page.get_by_text(text, exact=False).first.wait_for(
                        state="visible", timeout=min(timeout, 8000)
                    )
                    found = True
                    break
                except Exception as exc:
                    last_err = str(exc)
            duration_ms = (time.perf_counter() - t0) * 1000
            if not found:
                return on_fail(f"None of soft texts visible: {texts} ({last_err})")
            ctx.record_step_timing(
                index=idx, name=name, action=action, phase="assert", duration_ms=duration_ms, status="ok"
            )
            ctx.log_action("assert_pass", step=name, texts=texts, duration_ms=duration_ms)
            logger.info("[%s] PASS soft texts=%s", name, texts)
            return {}

        for text in texts:
            if not text:
                continue
            try:
                await page.get_by_text(text, exact=False).first.wait_for(
                    state="visible", timeout=timeout
                )
            except Exception as exc:
                return on_fail(f"Text not visible: {text!r} ({exc})")
        duration_ms = (time.perf_counter() - t0) * 1000
        ctx.record_step_timing(
            index=idx, name=name, action=action, phase="assert", duration_ms=duration_ms, status="ok"
        )
        ctx.log_action("assert_pass", step=name, texts=texts, duration_ms=duration_ms)
        logger.info("[%s] PASS texts=%s", name, texts)

    elif action == "assert_no_error_banner":
        # executed in actions when used as execute-phase; if assert-phase, no-op pass
        duration_ms = (time.perf_counter() - t0) * 1000
        ctx.record_step_timing(
            index=idx, name=name, action=action, phase="assert", duration_ms=duration_ms, status="ok"
        )
        ctx.log_action("assert_pass", step=name, duration_ms=duration_ms)

    return {}
