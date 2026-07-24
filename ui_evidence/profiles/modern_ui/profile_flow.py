"""Profile / subscription / admin-gate / lab-block flows."""
from __future__ import annotations

from typing import Any

from ui_evidence.profiles.modern_ui import routes as R
from ui_evidence.profiles.modern_ui.session import build_domain_prefix, checklist_from_steps


def build_profile_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    return [
        *prefix,
        {
            "action": "navigate_app",
            "path": R.PROFILE,
            "name": f"{n}. Deep-link profile",
        },
        {
            "action": "wait_for_module",
            "module": "Profile",
            "timeout_ms": 60000,
            "name": f"{n + 1}. Wait for profile module",
        },
        {
            "action": "assert_url_contains",
            "pattern": R.PROFILE,
            "name": f"{n + 2}. Assert profile URL",
        },
        {
            "action": "assert_no_error_banner",
            "soft": True,
            "name": f"{n + 3}. Soft-assert no error banner",
        },
        {"action": "screenshot", "name": f"{n + 4}. Screenshot — profile"},
        {
            "action": "navigate_app",
            "path": R.PRIVACY_POLICY,
            "name": f"{n + 5}. Deep-link privacy policy",
        },
        {
            "action": "wait_for_url",
            "pattern": "privacy",
            "timeout_ms": 30000,
            "name": f"{n + 6}. Wait for privacy URL",
        },
        {
            "action": "assert_url_contains",
            "pattern": "privacy",
            "name": f"{n + 7}. Assert privacy URL",
        },
        {"action": "screenshot", "name": f"{n + 8}. Screenshot — privacy"},
    ]


def build_subscription_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    return [
        *prefix,
        {
            "action": "navigate_app",
            "path": R.SUBSCRIPTION,
            "name": f"{n}. Deep-link subscription",
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
        {
            "action": "assert_text_visible",
            "texts": ["Subscription", "Plan", "Upgrade"],
            "soft": True,
            "name": f"{n + 3}. Soft-assert subscription chrome",
        },
        {"action": "screenshot", "name": f"{n + 4}. Screenshot — subscription"},
    ]


def build_admin_gate_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    expect_admin: bool = False,
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Non-admin: analysis/ai-chat redirect to dashboard. Admin: stay on route."""
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    steps = list(prefix)
    for path, label in ((R.ANALYSIS, "analysis"), (R.AI_CHAT, "ai-chat")):
        steps.extend(
            [
                {
                    "action": "navigate_app",
                    "path": path,
                    "name": f"{n}. Deep-link {path}",
                },
                {"action": "wait", "ms": 4000, "name": f"{n + 1}. Wait for redirect settle"},
            ]
        )
        if expect_admin:
            steps.append(
                {
                    "action": "assert_url_contains",
                    "pattern": path,
                    "name": f"{n + 2}. Assert admin stayed on {label}",
                }
            )
        else:
            steps.append(
                {
                    "action": "assert_url_contains",
                    "pattern": R.DASHBOARD,
                    "name": f"{n + 2}. Assert non-admin redirected from {label}",
                }
            )
        steps.append({"action": "screenshot", "name": f"{n + 3}. Screenshot — gate {label}"})
        n += 4

    # Lab always blocked
    steps.extend(
        [
            {
                "action": "navigate_app",
                "path": R.LAB,
                "name": f"{n}. Deep-link lab (should block)",
            },
            {"action": "wait", "ms": 3000, "name": f"{n + 1}. Wait for lab redirect"},
            {
                "action": "assert_url_contains",
                "pattern": R.DASHBOARD,
                "name": f"{n + 2}. Assert lab redirected to dashboard",
            },
            {"action": "screenshot", "name": f"{n + 3}. Screenshot — lab gate"},
        ]
    )
    return steps


def profile_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)
