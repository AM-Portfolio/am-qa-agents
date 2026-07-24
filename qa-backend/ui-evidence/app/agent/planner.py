from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AutonomousAgentState
from app.config import settings
from app.context import get_test_context
from app.profiles.registry import build_profile_steps, is_deterministic_profile
from app.profiles.modern_ui import routes as R

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = f"""You are a UI test planner for am-modern-ui (Flutter web).
Return ONLY valid JSON: an array of step objects. No markdown.

Valid app paths include: {R.DASHBOARD}, {R.PORTFOLIO}, {R.TRADE_DISCOVERY},
{R.MARKET}, {R.DOC_INTEL}, {R.PROFILE}, {R.SUBSCRIPTION}, {R.ANALYSIS}, {R.AI_CHAT}.

Allowed actions:
- navigate: {{"action":"navigate","url":"<full url>"}}
- navigate_app: {{"action":"navigate_app","path":"/app/dashboard"}}
- wait: {{"action":"wait","ms":2000}}
- wait_for_url: {{"action":"wait_for_url","pattern":"/app/dashboard","timeout_ms":45000}}
- wait_for_module: {{"action":"wait_for_module","module":"Portfolio","timeout_ms":60000}}
- wait_for_label: {{"action":"wait_for_label","label":"Email","timeout_ms":45000}}
- fill_label: {{"action":"fill_label","label":"Email","text":"..."}}
- click_button: {{"action":"click_button","name_match":"Sign In"}}
- click_nav: {{"action":"click_nav","title":"Portfolio"}}
- click_text: {{"action":"click_text","text":"Overview"}}
- screenshot: {{"action":"screenshot"}}
- assert_title_not_empty: {{"action":"assert_title_not_empty"}}
- assert_url_contains: {{"action":"assert_url_contains","pattern":"/app/dashboard"}}
- assert_text_visible: {{"action":"assert_text_visible","texts":["Dashboard"],"soft":true}}
- assert_no_error_banner: {{"action":"assert_no_error_banner"}}
- click: {{"action":"click","selector":"<css>"}}
- fill: {{"action":"fill","selector":"<css>","text":"<value>"}}

Prefer navigate_app deep-links over click_nav for reliability. Keep steps minimal."""


def default_smoke_steps(target_url: str) -> list[dict[str, Any]]:
    return [
        {"action": "navigate", "url": target_url, "name": "Open target URL"},
        {"action": "wait", "ms": 2000, "name": "Wait for page load"},
        {"action": "screenshot", "name": "Page screenshot"},
        {"action": "assert_title_not_empty", "name": "Title not empty"},
    ]


def _parse_steps(raw: str) -> list[dict[str, Any]]:
    import json
    import re

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("Planner must return a JSON array of steps")
    return data


async def plan_steps(
    *,
    target_url: str,
    specification: str,
    profile: str,
    ctx,
) -> list[dict[str, Any]]:
    if is_deterministic_profile(profile):
        steps = build_profile_steps(
            profile,
            target_url=target_url,
            email=settings.TEST_USER_EMAIL,
            password=settings.TEST_USER_PASSWORD,
            ui_mode=settings.UI_APP_MODE,
            login_mode=settings.AUTH_LOGIN_MODE,
            portfolio_id=settings.TEST_PORTFOLIO_ID,
        )
        logger.info("Using deterministic profile %s (%d steps) for %s", profile, len(steps), target_url)
        return steps

    if not specification.strip():
        logger.info("No specification — using default %s smoke steps", profile)
        return default_smoke_steps(target_url)

    user_prompt = (
        f"Target URL: {target_url}\n"
        f"Profile: {profile}\n"
        f"Test specification:\n{specification}\n\n"
        "Produce the JSON step array."
    )
    raw = await ctx.llm_client.chat_text(
        system=PLANNER_SYSTEM,
        user=user_prompt,
        model=settings.LLM_PLANNER_MODEL,
        session_id=ctx.session_id,
        test_id=ctx.test_id,
        temperature=0.1,
    )
    try:
        return _parse_steps(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Planner JSON invalid (%s) — falling back to smoke steps", exc)
        return default_smoke_steps(target_url)


async def planner_node(state: AutonomousAgentState, config: RunnableConfig) -> dict[str, Any]:
    ctx = get_test_context(config)
    logger.info("Planning test profile=%s", ctx.profile)

    steps = await plan_steps(
        target_url=state["target_url"],
        specification=state.get("specification") or "",
        profile=ctx.profile,
        ctx=ctx,
    )
    ctx.log_action("plan", step_count=len(steps), profile=ctx.profile)
    return {
        "steps": steps,
        "current_step_index": 0,
        "failures_encountered": [],
        "screenshot_labels": [],
    }
