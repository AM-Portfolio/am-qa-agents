"""Profile registry — central dispatch for deterministic test step builders."""
from __future__ import annotations

from typing import Any, Callable

from ui_evidence.profiles.base import TargetConfig
from ui_evidence.features.feature_catalog import (
    auth_user_full_flow_profiles,
    auth_user_module_profiles,
)
from ui_evidence.profiles.modern_ui.auth_flow import (
    auth_verification_checklist,
    build_auth_flow_steps,
)
from ui_evidence.profiles.modern_ui.auth_scenarios import (
    AUTH_SCENARIO_BUILDERS,
    auth_scenario_verification_checklist,
)
from ui_evidence.profiles.modern_ui.subscription_scenarios import (
    SUBSCRIPTION_SCENARIO_BUILDERS,
    subscription_scenario_verification_checklist,
)
from ui_evidence.profiles.modern_ui.dashboard_flow import (
    build_dashboard_flow_steps,
    dashboard_verification_checklist,
)
from ui_evidence.profiles.modern_ui.doc_intel_flow import (
    build_doc_intel_flow_steps,
    build_doc_upload_flow_steps,
    doc_intel_verification_checklist,
)
from ui_evidence.profiles.modern_ui.market_flow import (
    build_market_dev_flow_steps,
    build_market_flow_steps,
    build_market_gate_flow_steps,
    build_market_user_flow_steps,
    market_verification_checklist,
)
from ui_evidence.profiles.modern_ui.portfolio_flow import (
    build_portfolio_flow_steps,
    build_portfolio_tabs_flow_steps,
    portfolio_verification_checklist,
)
from ui_evidence.profiles.modern_ui.profile_flow import (
    build_admin_gate_flow_steps,
    build_profile_flow_steps,
    build_subscription_flow_steps,
    profile_verification_checklist,
)
from ui_evidence.profiles.modern_ui.trade_flow import (
    build_trade_flow_steps,
    build_trade_tabs_flow_steps,
    trade_verification_checklist,
)

AUTH_PROFILES = frozenset({"AUTH_FLOW", "AUTH_FLOW_MAIN", "AUTH_FLOW_PORTFOLIO"})
AUTH_SCENARIO_PROFILES = frozenset(AUTH_SCENARIO_BUILDERS.keys())
SUBSCRIPTION_SCENARIO_PROFILES = frozenset(SUBSCRIPTION_SCENARIO_BUILDERS.keys())

PROFILE_BUILDERS: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "AUTH_FLOW": build_auth_flow_steps,
    "AUTH_FLOW_MAIN": build_auth_flow_steps,
    "AUTH_FLOW_PORTFOLIO": build_auth_flow_steps,
    **AUTH_SCENARIO_BUILDERS,
    **SUBSCRIPTION_SCENARIO_BUILDERS,
    "DASHBOARD_SMOKE_FLOW": build_dashboard_flow_steps,
    "PORTFOLIO_SMOKE_FLOW": build_portfolio_flow_steps,
    "PORTFOLIO_TABS_FLOW": build_portfolio_tabs_flow_steps,
    "MARKET_SMOKE_FLOW": build_market_flow_steps,
    "MARKET_USER_FLOW": build_market_user_flow_steps,
    "MARKET_DEV_FLOW": build_market_dev_flow_steps,
    "MARKET_GATE_FLOW": build_market_gate_flow_steps,
    "TRADE_SMOKE_FLOW": build_trade_flow_steps,
    "TRADE_TABS_FLOW": build_trade_tabs_flow_steps,
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
    **{name: auth_scenario_verification_checklist for name in AUTH_SCENARIO_BUILDERS},
    **{
        name: subscription_scenario_verification_checklist
        for name in SUBSCRIPTION_SCENARIO_BUILDERS
    },
    "DASHBOARD_SMOKE_FLOW": dashboard_verification_checklist,
    "PORTFOLIO_SMOKE_FLOW": portfolio_verification_checklist,
    "PORTFOLIO_TABS_FLOW": portfolio_verification_checklist,
    "MARKET_SMOKE_FLOW": market_verification_checklist,
    "MARKET_USER_FLOW": market_verification_checklist,
    "MARKET_DEV_FLOW": market_verification_checklist,
    "MARKET_GATE_FLOW": market_verification_checklist,
    "TRADE_SMOKE_FLOW": trade_verification_checklist,
    "TRADE_TABS_FLOW": trade_verification_checklist,
    "DOC_INTEL_SMOKE_FLOW": doc_intel_verification_checklist,
    "DOC_UPLOAD_FLOW": doc_intel_verification_checklist,
    "PROFILE_SMOKE_FLOW": profile_verification_checklist,
    "SUBSCRIPTION_SMOKE_FLOW": profile_verification_checklist,
    "ADMIN_GATE_FLOW": profile_verification_checklist,
}

SMOKE_SUITE_PROFILES = (
    "AUTH_FLOW_MAIN",
    "DASHBOARD_SMOKE_FLOW",
    "PORTFOLIO_SMOKE_FLOW",
)

RELEASE_GATE_PROFILES = (
    "AUTH_FLOW_MAIN",
    "DASHBOARD_SMOKE_FLOW",
    "PORTFOLIO_SMOKE_FLOW",
    "MARKET_USER_FLOW",
    "TRADE_SMOKE_FLOW",
    "DOC_INTEL_SMOKE_FLOW",
)

# Prod read-only full UI: credentials login, all live sidebars, no upload / Add Trade / market admin.
PROD_UI_FULL_PROFILES = (
    "AUTH_FLOW_MAIN",
    "DASHBOARD_SMOKE_FLOW",
    "PORTFOLIO_SMOKE_FLOW",
    "PORTFOLIO_TABS_FLOW",
    "TRADE_SMOKE_FLOW",
    "TRADE_TABS_FLOW",
    "MARKET_USER_FLOW",
    "MARKET_GATE_FLOW",
    "DOC_INTEL_SMOKE_FLOW",
    "PROFILE_SMOKE_FLOW",
    "SUBSCRIPTION_SMOKE_FLOW",
    "ADMIN_GATE_FLOW",
)

# Cucumber-style auth module — order from features/auth/*.feature
AUTH_USER_MODULE_PROFILES = auth_user_module_profiles()

# Full auth/user/subscription UI flows (see docs/AUTH_USER_FLOW_CATALOG.md)
AUTH_USER_FULL_FLOW_PROFILES = auth_user_full_flow_profiles()

# Auth + users/profile + subscription smoke (complete login module pack)
def _auth_users_subs_module_profiles() -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for name in (
        *AUTH_USER_FULL_FLOW_PROFILES,
        "PROFILE_SMOKE_FLOW",
        "SUBSCRIPTION_SMOKE_FLOW",
    ):
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return tuple(out)


AUTH_USERS_SUBS_MODULE_PROFILES = _auth_users_subs_module_profiles()

# Subscription-only modern-ui (productized merge gate — no full auth)
SUBSCRIPTION_MODULE_PROFILES = (
    "SUB_UI_OPEN",
    "SUB_UI_PLANS",
    "SUB_UI_TIME_LEFT",
    "SUBSCRIPTION_SMOKE_FLOW",
)

# Identity API scenarios (prod Swagger → OpenAPI MCP tools). Not Playwright profiles —
# executed via ui_evidence.api.run_auth_api_scenarios.
AUTH_API_MODULE_SCENARIOS = (
    "AUTH_API_HEALTH",
    "AUTH_API_LOGIN",
    "AUTH_API_USERS_ME",
    "AUTH_API_FORGOT_SCHEMA",
    "AUTH_API_REGISTER_SCHEMA",
)

SUITE_PROFILES: dict[str, tuple[str, ...]] = {
    "smoke": SMOKE_SUITE_PROFILES,
    "release_gate": RELEASE_GATE_PROFILES,
    "prod_ui_full": PROD_UI_FULL_PROFILES,
    "auth_user_module": AUTH_USER_MODULE_PROFILES,
    "auth_user_full_flows": AUTH_USER_FULL_FLOW_PROFILES,
    "auth_users_subs_module": AUTH_USERS_SUBS_MODULE_PROFILES,
    "subscription_module": SUBSCRIPTION_MODULE_PROFILES,
    # API-only identity module (tool names, not UI builders)
    "auth_api_module": AUTH_API_MODULE_SCENARIOS,
}

DETERMINISTIC_PROFILES = (
    frozenset(PROFILE_BUILDERS.keys())
    | AUTH_PROFILES
    | AUTH_SCENARIO_PROFILES
    | SUBSCRIPTION_SCENARIO_PROFILES
)


def profile_for_mode(ui_mode: str) -> str:
    return "AUTH_FLOW_MAIN" if ui_mode == "main" else "AUTH_FLOW_PORTFOLIO"


def is_auth_profile(profile: str) -> bool:
    return (
        profile in AUTH_PROFILES
        or profile in AUTH_SCENARIO_PROFILES
        or profile in SUBSCRIPTION_SCENARIO_PROFILES
    )


def is_deterministic_profile(profile: str) -> bool:
    return profile in DETERMINISTIC_PROFILES


def suite_profiles(suite: str) -> tuple[str, ...]:
    profiles = SUITE_PROFILES.get(suite)
    if profiles is None:
        raise ValueError(f"Unknown suite: {suite}")
    return profiles


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
