"""Dashboard smoke — login then deep-link /app/dashboard."""
from __future__ import annotations

from typing import Any

from ui_evidence.profiles.modern_ui import routes as R
from ui_evidence.profiles.modern_ui.session import build_domain_prefix, checklist_from_steps


def build_dashboard_flow_steps(
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
            "path": R.DASHBOARD,
            "name": f"{n}. Deep-link {R.DASHBOARD}",
        },
        {
            "action": "wait_for_module",
            "module": "Dashboard",
            "timeout_ms": 60000,
            "name": f"{n + 1}. Wait for dashboard module",
        },
        {
            "action": "assert_url_contains",
            "pattern": R.DASHBOARD,
            "name": f"{n + 2}. Assert dashboard URL",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Dashboard"],
            "soft": True,
            "name": f"{n + 3}. Soft-assert Dashboard label",
        },
        {
            "action": "assert_no_error_banner",
            "soft": True,
            "name": f"{n + 4}. Soft-assert no error banner",
        },
        {"action": "screenshot", "name": f"{n + 5}. Screenshot — dashboard"},
    ]


def dashboard_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)
