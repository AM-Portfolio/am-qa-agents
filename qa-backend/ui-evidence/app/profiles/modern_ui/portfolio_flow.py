"""Portfolio smoke + tab-sweep — deep-link first."""
from __future__ import annotations

from typing import Any

from app.profiles.modern_ui import routes as R
from app.profiles.modern_ui.session import build_domain_prefix, checklist_from_steps


def _portfolio_entry_path(portfolio_id: str | None) -> str:
    if portfolio_id:
        return R.portfolio_path(portfolio_id, "overview")
    return R.portfolio_legacy_tab_path("overview")


def build_portfolio_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    portfolio_id: str | None = None,
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    path = _portfolio_entry_path(portfolio_id)
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    return [
        *prefix,
        {
            "action": "navigate_app",
            "path": path,
            "name": f"{n}. Deep-link {path}",
        },
        {
            "action": "wait_for_module",
            "module": "Portfolio",
            "timeout_ms": 90000,
            "name": f"{n + 1}. Wait for portfolio module",
        },
        {
            "action": "assert_url_contains",
            "pattern": "/app/portfolio",
            "name": f"{n + 2}. Assert portfolio URL",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Overview"],
            "soft": True,
            "name": f"{n + 3}. Soft-assert Overview",
        },
        {
            "action": "assert_no_error_banner",
            "soft": True,
            "name": f"{n + 4}. Soft-assert no error banner",
        },
        {"action": "screenshot", "name": f"{n + 5}. Screenshot — portfolio overview"},
    ]


def build_portfolio_tabs_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    portfolio_id: str | None = None,
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    steps = build_portfolio_flow_steps(
        target_url=target_url,
        email=email,
        password=password,
        login_mode=login_mode,
        portfolio_id=portfolio_id,
    )
    n = len(steps) + 1
    for tab in R.PORTFOLIO_TABS:
        if tab == "overview":
            continue
        path = (
            R.portfolio_path(portfolio_id, tab)
            if portfolio_id
            else R.portfolio_legacy_tab_path(tab)
        )
        steps.extend(
            [
                {
                    "action": "navigate_app",
                    "path": path,
                    "name": f"{n}. Deep-link portfolio tab {tab}",
                },
                {
                    "action": "wait_for_url",
                    "pattern": tab,
                    "timeout_ms": 45000,
                    "name": f"{n + 1}. Wait for tab slug {tab}",
                },
                {
                    "action": "assert_url_contains",
                    "pattern": tab,
                    "name": f"{n + 2}. Assert tab {tab} in URL",
                },
                {"action": "screenshot", "name": f"{n + 3}. Screenshot — portfolio/{tab}"},
            ]
        )
        n += 4
    return steps


def portfolio_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)
