"""Cucumber-style auth Feature ↔ Scenario profile sync."""
from __future__ import annotations

from ui_evidence.features.feature_catalog import (
    AUTH_FEATURE_FILES,
    auth_feature_scenarios,
    auth_user_full_flow_profiles,
    auth_user_module_profiles,
)
from ui_evidence.profiles.registry import (
    AUTH_SCENARIO_PROFILES,
    AUTH_USER_MODULE_PROFILES,
    PROFILE_BUILDERS,
    SUBSCRIPTION_SCENARIO_PROFILES,
    is_deterministic_profile,
    suite_profiles,
)
from ui_evidence.profiles.modern_ui.auth_scenarios import AUTH_SCENARIO_BUILDERS
from ui_evidence.profiles.modern_ui.subscription_scenarios import (
    SUBSCRIPTION_SCENARIO_BUILDERS,
)


def test_auth_feature_files_map_to_profiles():
    rows = auth_feature_scenarios()
    assert len(rows) >= 9
    profiles = [p for _, _, p in rows]
    assert len(profiles) == len(set(profiles)), "duplicate @profile tags"
    for feature_rel, scenario, profile in rows:
        assert feature_rel in AUTH_FEATURE_FILES or feature_rel.replace("\\", "/") in {
            f.replace("\\", "/") for f in AUTH_FEATURE_FILES
        }
        assert scenario
        assert profile in AUTH_SCENARIO_BUILDERS
        assert profile in PROFILE_BUILDERS
        assert is_deterministic_profile(profile)


def test_auth_user_module_suite_order_matches_features():
    from_features = auth_user_module_profiles()
    assert suite_profiles("auth_user_module") == from_features
    assert AUTH_USER_MODULE_PROFILES == from_features
    # Flow: registration → login → forgot → Google
    assert from_features[0].startswith("AUTH_REG_")
    assert "AUTH_LOGIN_OK" in from_features
    assert "AUTH_FORGOT_SUBMIT" in from_features
    assert from_features[-1] == "AUTH_GOOGLE_REDIRECT"
    assert set(from_features) <= AUTH_SCENARIO_PROFILES


def test_auth_scenario_builders_emit_steps():
    steps = PROFILE_BUILDERS["AUTH_REG_OPEN"](
        target_url="https://am.asrax.in",
        email="u@test.com",
        password="x",
        profile="AUTH_REG_OPEN",
        ui_mode="main",
        login_mode="credentials",
    )
    assert steps[0]["action"] == "navigate"
    assert "/register" in steps[0]["url"]
    assert any(s.get("action") == "assert_text_visible" for s in steps)


def test_auth_user_full_flows_suite_includes_sessions_and_subscription():
    profiles = auth_user_full_flow_profiles()
    assert suite_profiles("auth_user_full_flows") == profiles
    assert "AUTH_LOGOUT_UI" in profiles
    assert "AUTH_SESSIONS_LIST_UI" in profiles
    assert "SUB_UI_TIME_LEFT" in profiles
    assert "AUTH_REG_SUBMIT_NONPROD" in profiles
    for p in profiles:
        assert p in PROFILE_BUILDERS
        assert is_deterministic_profile(p)
    assert set(SUBSCRIPTION_SCENARIO_BUILDERS) <= SUBSCRIPTION_SCENARIO_PROFILES
    assert set(AUTH_SCENARIO_BUILDERS) <= AUTH_SCENARIO_PROFILES


def test_auth_users_subs_module_includes_profile_and_subscription_smoke():
    profiles = suite_profiles("auth_users_subs_module")
    assert "PROFILE_SMOKE_FLOW" in profiles
    assert "SUBSCRIPTION_SMOKE_FLOW" in profiles
    full = suite_profiles("auth_user_full_flows")
    assert set(full) <= set(profiles)
    assert profiles[-2:] == ("PROFILE_SMOKE_FLOW", "SUBSCRIPTION_SMOKE_FLOW") or (
        "PROFILE_SMOKE_FLOW" in profiles and "SUBSCRIPTION_SMOKE_FLOW" in profiles
    )


def test_subscription_module_suite_matches_catalog():
    from pathlib import Path

    import yaml

    from ui_evidence.profiles.registry import SUBSCRIPTION_MODULE_PROFILES

    profiles = suite_profiles("subscription_module")
    assert profiles == SUBSCRIPTION_MODULE_PROFILES
    assert profiles == (
        "SUB_UI_OPEN",
        "SUB_UI_PLANS",
        "SUB_UI_TIME_LEFT",
        "SUBSCRIPTION_SMOKE_FLOW",
    )
    catalog = Path(__file__).resolve().parents[1] / "catalog" / "subscription_module.yaml"
    data = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    assert data["suite"] == "subscription_module"
    assert data["api_pack"] == "subscription"
    assert tuple(data["ui_profiles"]) == profiles
    for p in profiles:
        assert p in PROFILE_BUILDERS
        assert is_deterministic_profile(p)
