"""Subscription Feature Scenario builders (plans / time left)."""
from __future__ import annotations

from typing import Any

from ui_evidence.profiles.modern_ui import routes as R
from ui_evidence.profiles.modern_ui.session import build_domain_prefix, checklist_from_steps


def _subscription_base(
    *,
    target_url: str,
    email: str,
    password: str,
    login_mode: str,
) -> tuple[list[dict[str, Any]], int]:
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    steps = [
        *prefix,
        {
            "action": "navigate_app",
            "path": R.SUBSCRIPTION,
            "name": f"{n}. Open subscription",
        },
        {
            "action": "wait_for_url",
            "pattern": R.SUBSCRIPTION,
            "timeout_ms": 45000,
            "name": f"{n + 1}. Wait for subscription URL",
        },
        {
            "action": "assert_url_contains",
            "pattern": R.SUBSCRIPTION,
            "name": f"{n + 2}. Assert subscription URL",
        },
    ]
    return steps, n + 3


def build_sub_ui_open_steps(
    *,
    target_url: str,
    email: str,
    password: str,
    login_mode: str = "credentials",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    steps, n = _subscription_base(
        target_url=target_url, email=email, password=password, login_mode=login_mode
    )
    return [
        *steps,
        {
            "action": "assert_text_visible",
            "texts": ["Subscription", "Plan", "Upgrade", "Billing"],
            "soft": True,
            "name": f"{n}. Soft assert subscription chrome",
        },
        {"action": "screenshot", "name": f"{n + 1}. Screenshot — subscription open"},
    ]


def build_sub_ui_plans_steps(
    *,
    target_url: str,
    email: str,
    password: str,
    login_mode: str = "credentials",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    steps, n = _subscription_base(
        target_url=target_url, email=email, password=password, login_mode=login_mode
    )
    return [
        *steps,
        {
            "action": "assert_text_visible",
            "texts": ["Free", "Pro", "Plan", "Upgrade", "Monthly", "Yearly"],
            "soft": True,
            "name": f"{n}. Soft assert plan cards / tiers",
        },
        {"action": "screenshot", "name": f"{n + 1}. Screenshot — plans"},
    ]


def build_sub_ui_time_left_steps(
    *,
    target_url: str,
    email: str,
    password: str,
    login_mode: str = "credentials",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    steps, n = _subscription_base(
        target_url=target_url, email=email, password=password, login_mode=login_mode
    )
    return [
        *steps,
        {
            "action": "assert_text_visible",
            "texts": [
                "day",
                "days",
                "left",
                "expires",
                "trial",
                "renew",
                "remaining",
                "until",
            ],
            "soft": True,
            "name": f"{n}. Soft assert time-left / trial / renew copy",
        },
        {"action": "screenshot", "name": f"{n + 1}. Screenshot — time left"},
    ]


SUBSCRIPTION_SCENARIO_BUILDERS: dict[str, Any] = {
    "SUB_UI_OPEN": build_sub_ui_open_steps,
    "SUB_UI_PLANS": build_sub_ui_plans_steps,
    "SUB_UI_TIME_LEFT": build_sub_ui_time_left_steps,
}


def subscription_scenario_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)
