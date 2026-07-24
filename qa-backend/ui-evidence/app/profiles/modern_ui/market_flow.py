"""Market smoke + tab visits — deep-link first."""
from __future__ import annotations

from typing import Any

from app.profiles.modern_ui import routes as R
from app.profiles.modern_ui.session import build_domain_prefix, checklist_from_steps


def build_market_flow_steps(
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
    steps = [
        *prefix,
        {
            "action": "navigate_app",
            "path": R.market_path("all-indices"),
            "name": f"{n}. Deep-link market all-indices",
        },
        {
            "action": "wait_for_module",
            "module": "Market",
            "timeout_ms": 90000,
            "name": f"{n + 1}. Wait for market module",
        },
        {
            "action": "assert_url_contains",
            "pattern": "/app/market",
            "name": f"{n + 2}. Assert market URL",
        },
        {
            "action": "assert_no_error_banner",
            "soft": True,
            "name": f"{n + 3}. Soft-assert no error banner",
        },
        {"action": "screenshot", "name": f"{n + 4}. Screenshot — market all-indices"},
    ]
    n = len(steps) + 1
    for slug in ("dashboard", "heatmap-explorer"):
        path = R.market_path(slug)
        steps.extend(
            [
                {
                    "action": "navigate_app",
                    "path": path,
                    "name": f"{n}. Deep-link {path}",
                },
                {
                    "action": "wait_for_url",
                    "pattern": slug,
                    "timeout_ms": 45000,
                    "name": f"{n + 1}. Wait for market slug {slug}",
                },
                {
                    "action": "assert_url_contains",
                    "pattern": slug,
                    "name": f"{n + 2}. Assert {slug} in URL",
                },
                {"action": "screenshot", "name": f"{n + 3}. Screenshot — market/{slug}"},
            ]
        )
        n += 4
    return steps


def market_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)
