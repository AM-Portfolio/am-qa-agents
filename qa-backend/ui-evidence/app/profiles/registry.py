"""Profile registry — central dispatch for deterministic test step builders."""
from __future__ import annotations

from typing import Any, Callable

from app.profiles.base import TargetConfig
from app.profiles.modern_ui.auth_flow import (
    auth_verification_checklist,
    build_auth_flow_steps,
)
from app.profiles.modern_ui.dashboard_flow import (
    build_dashboard_flow_steps,
    dashboard_verification_checklist,
)
from app.profiles.modern_ui.doc_intel_flow import (
    build_doc_intel_flow_steps,
    build_doc_upload_flow_steps,
    doc_intel_verification_checklist,
)
from app.profiles.modern_ui.market_flow import (
    build_market_flow_steps,
    market_verification_checklist,
)
from app.profiles.modern_ui.portfolio_flow import (
    build_portfolio_flow_steps,
    build_portfolio_tabs_flow_steps,
    portfolio_verification_checklist,
)
from app.profiles.modern_ui.profile_flow import (
    build_admin_gate_flow_steps,
    build_profile_flow_steps,
    build_subscription_flow_steps,
    profile_verification_checklist,
)
from app.profiles.modern_ui.trade_flow import (
    build_trade_flow_steps,
    trade_verification_checklist,
)

AUTH_PROFILES = frozenset({"AUTH_FLOW", "AUTH_FLOW_MAIN", "AUTH_FLOW_PORTFOLIO"})

PROFILE_BUILDERS: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "AUTH_FLOW": build_auth_flow_steps,
    "AUTH_FLOW_MAIN": build_auth_flow_steps,
    "AUTH_FLOW_PORTFOLIO": build_auth_flow_steps,
    "DASHBOARD_SMOKE_FLOW": build_dashboard_flow_steps,
    "PORTFOLIO_SMOKE_FLOW": build_portfolio_flow_steps,
    "PORTFOLIO_TABS_FLOW": build_portfolio_tabs_flow_steps,
    "MARKET_SMOKE_FLOW": build_market_flow_steps,
    "TRADE_SMOKE_FLOW": build_trade_flow_steps,
    "DOC_INTEL_SMOKE_FLOW": build_doc_intel_flow_steps,
    "DOC_UPLOAD_FLOW": build_doc_upload_flow_steps,
    "PROFILE_SMOKE_FLOW": build_profile_flow_steps,
    "SUBSCRIPTION_SMOKE_FLOW": build_subscription_flow_steps,
    "ADMIN_GATE_FLOW": build_admin_gate_flow_steps,
}

CHECKLIST_BUILDERS: dict[str, Callable[..., list[dict[str, str]]]] = {
    "AUTH_FLOW": auth_verification_checklist,
    "AUTH_FLOW_MAIN": auth_verification_checklist,
    "AUTH_FLOW_PORTFOLIO": auth_verification_checklist,
    "DASHBOARD_SMOKE_FLOW": dashboard_verification_checklist,
    "PORTFOLIO_SMOKE_FLOW": portfolio_verification_checklist,
    "PORTFOLIO_TABS_FLOW": portfolio_verification_checklist,
    "MARKET_SMOKE_FLOW": market_verification_checklist,
    "TRADE_SMOKE_FLOW": trade_verification_checklist,
    "DOC_INTEL_SMOKE_FLOW": doc_intel_verification_checklist,
    "DOC_UPLOAD_FLOW": doc_intel_verification_checklist,
    "PROFILE_SMOKE_FLOW": profile_verification_checklist,
    "SUBSCRIPTION_SMOKE_FLOW": profile_verification_checklist,
    "ADMIN_GATE_FLOW": profile_verification_checklist,
}

RELEASE_GATE_PROFILES = (
    "AUTH_FLOW_MAIN",
    "DASHBOARD_SMOKE_FLOW",
    "PORTFOLIO_SMOKE_FLOW",
    "MARKET_SMOKE_FLOW",
    "TRADE_SMOKE_FLOW",
    "DOC_INTEL_SMOKE_FLOW",
)

DETERMINISTIC_PROFILES = frozenset(PROFILE_BUILDERS.keys()) | AUTH_PROFILES


def profile_for_mode(ui_mode: str) -> str:
    return "AUTH_FLOW_MAIN" if ui_mode == "main" else "AUTH_FLOW_PORTFOLIO"


def is_auth_profile(profile: str) -> bool:
    return profile in AUTH_PROFILES


def is_deterministic_profile(profile: str) -> bool:
    return profile in DETERMINISTIC_PROFILES


def build_profile_steps(
    profile: str,
    *,
    target_url: str,
    email: str,
    password: str,
    ui_mode: str = "main",
    login_mode: str = "demo",
    portfolio_id: str | None = None,
    upload_file: str | None = None,
    expect_admin: bool = False,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    builder = PROFILE_BUILDERS.get(profile)
    if builder is None:
        raise ValueError(f"Unknown deterministic profile: {profile}")
    return builder(
        target_url=target_url,
        email=email,
        password=password,
        profile=profile,
        ui_mode=ui_mode,
        login_mode=login_mode,
        portfolio_id=portfolio_id,
        upload_file=upload_file,
        expect_admin=expect_admin,
        **kwargs,
    )


def build_steps_from_target(
    target: TargetConfig,
    *,
    email: str,
    password: str,
) -> list[dict[str, Any]]:
    return build_profile_steps(
        target.profile,
        target_url=target.base_url,
        email=email,
        password=password,
        ui_mode=target.ui_mode,
        login_mode=target.auth_login_mode,
        portfolio_id=target.portfolio_id,
        expect_admin=target.persona == "admin_user",
    )


def verification_checklist(
    profile: str,
    steps: list[dict[str, Any]],
    action_log: list[dict[str, Any]],
) -> list[dict[str, str]]:
    fn = CHECKLIST_BUILDERS.get(profile)
    if fn is None:
        return []
    return fn(steps, action_log)
