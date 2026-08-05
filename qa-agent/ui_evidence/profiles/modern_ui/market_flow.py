"""Market user / developer / gate flows — deep-link first. Skip mutating admin tools."""
from __future__ import annotations

from typing import Any

from ui_evidence.profiles.modern_ui import routes as R
from ui_evidence.profiles.modern_ui.session import build_domain_prefix, checklist_from_steps


def _visit_slugs(
    steps: list[dict[str, Any]],
    *,
    slugs: tuple[str, ...],
    start_n: int,
) -> list[dict[str, Any]]:
    n = start_n
    for slug in slugs:
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
                {
                    "action": "assert_no_error_banner",
                    "soft": True,
                    "name": f"{n + 3}. Soft-assert no error on {slug}",
                },
                {"action": "screenshot", "name": f"{n + 4}. Screenshot — market/{slug}"},
            ]
        )
        n += 5
    return steps


def build_market_user_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Non-admin Market sidebar: dashboard + market-analysis."""
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    steps: list[dict[str, Any]] = [
        *prefix,
        {
            "action": "navigate_app",
            "path": R.market_path("dashboard"),
            "name": f"{n}. Deep-link market dashboard",
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
        {"action": "screenshot", "name": f"{n + 4}. Screenshot — market dashboard"},
    ]
    return _visit_slugs(steps, slugs=("market-analysis",), start_n=len(steps) + 1)


def build_market_dev_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Admin developer-mode explorers (view-only). Skips price-test/admin/developer-dashboard."""
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    steps: list[dict[str, Any]] = [
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
        {"action": "screenshot", "name": f"{n + 3}. Screenshot — market all-indices"},
    ]
    return _visit_slugs(
        steps,
        slugs=tuple(s for s in R.MARKET_DEV_SLUGS if s != "all-indices"),
        start_n=len(steps) + 1,
    )


def build_market_gate_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Non-admin: deep-link admin/streamer tools → expect redirect to dashboard."""
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    steps: list[dict[str, Any]] = list(prefix)
    for slug in ("admin", "streamer"):
        path = R.market_path(slug)
        steps.extend(
            [
                {
                    "action": "navigate_app",
                    "path": path,
                    "name": f"{n}. Deep-link gated {path}",
                },
                {"action": "wait", "ms": 4000, "name": f"{n + 1}. Wait for market gate settle"},
                {
                    "action": "assert_url_contains",
                    "pattern": "dashboard",
                    "name": f"{n + 2}. Assert non-admin redirected from {slug}",
                },
                {"action": "screenshot", "name": f"{n + 3}. Screenshot — market gate {slug}"},
            ]
        )
        n += 4
    return steps


def build_market_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Backward-compatible alias: user-mode market flow (dashboard + market-analysis)."""
    return build_market_user_flow_steps(
        target_url=target_url,
        email=email,
        password=password,
        login_mode=login_mode,
        **_kwargs,
    )


def market_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)
