"""Trade discovery smoke — deep-link /app/trade/portfolios."""
from __future__ import annotations

from typing import Any

from ui_evidence.profiles.modern_ui import routes as R
from ui_evidence.profiles.modern_ui.session import build_domain_prefix, checklist_from_steps


def build_trade_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    portfolio_id: str | None = None,
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    steps = [
        *prefix,
        {
            "action": "navigate_app",
            "path": R.TRADE_DISCOVERY,
            "name": f"{n}. Deep-link trade discovery",
        },
        {
            "action": "wait_for_module",
            "module": "Trade",
            "timeout_ms": 90000,
            "name": f"{n + 1}. Wait for trade module",
        },
        {
            "action": "assert_url_contains",
            "pattern": "/app/trade",
            "name": f"{n + 2}. Assert trade URL",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Trade", "Portfolios"],
            "soft": True,
            "name": f"{n + 3}. Soft-assert Trade shell",
        },
        {
            "action": "assert_no_error_banner",
            "soft": True,
            "name": f"{n + 4}. Soft-assert no error banner",
        },
        {"action": "screenshot", "name": f"{n + 5}. Screenshot — trade discovery"},
    ]
    if portfolio_id:
        n = len(steps) + 1
        path = R.trade_path(portfolio_id, "calendar")
        steps.extend(
            [
                {
                    "action": "navigate_app",
                    "path": path,
                    "name": f"{n}. Deep-link trade calendar",
                },
                {
                    "action": "wait_for_url",
                    "pattern": "calendar",
                    "timeout_ms": 45000,
                    "name": f"{n + 1}. Wait for calendar tab",
                },
                {
                    "action": "assert_url_contains",
                    "pattern": "calendar",
                    "name": f"{n + 2}. Assert calendar in URL",
                },
                {"action": "screenshot", "name": f"{n + 3}. Screenshot — trade calendar"},
            ]
        )
    return steps


def trade_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)
