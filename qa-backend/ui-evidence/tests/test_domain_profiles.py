from app.profiles.registry import (
    DETERMINISTIC_PROFILES,
    RELEASE_GATE_PROFILES,
    build_profile_steps,
    is_deterministic_profile,
)
from app.profiles.modern_ui import routes as R
from app.profiles.modern_ui.auth_flow import build_auth_flow_steps, detect_ui_mode


def test_auth_profiles_still_deterministic():
    assert is_deterministic_profile("AUTH_FLOW_MAIN")
    assert is_deterministic_profile("PORTFOLIO_SMOKE_FLOW")
    assert "DASHBOARD_SMOKE_FLOW" in DETERMINISTIC_PROFILES


def test_release_gate_profiles():
    assert "AUTH_FLOW_MAIN" in RELEASE_GATE_PROFILES
    assert "PORTFOLIO_SMOKE_FLOW" in RELEASE_GATE_PROFILES


def test_portfolio_auth_steps_demo_login():
    steps = build_auth_flow_steps(
        target_url="http://localhost:9005",
        email="user@test.com",
        password="secret",
        profile="AUTH_FLOW",
        ui_mode="portfolio",
        login_mode="demo",
    )
    assert steps[0]["action"] == "navigate"
    assert any(s["action"] == "click_demo_login" for s in steps)


def test_main_auth_uses_dashboard_path():
    steps = build_auth_flow_steps(
        target_url="http://localhost:9000",
        email="a@b.com",
        password="x",
        profile="AUTH_FLOW_MAIN",
        ui_mode="portfolio",
        login_mode="demo",
    )
    assert any(
        "/app/dashboard" in s.get("pattern", "")
        for s in steps
        if s["action"] == "assert_url_contains"
    )


def test_detect_ui_mode_from_port():
    assert detect_ui_mode("http://localhost:9000", "AUTH_FLOW", "portfolio") == "main"
    assert detect_ui_mode("http://localhost:9005", "AUTH_FLOW", "main") == "portfolio"


def test_dashboard_smoke_deep_link():
    steps = build_profile_steps(
        "DASHBOARD_SMOKE_FLOW",
        target_url="http://localhost:9000",
        email="a@b.com",
        password="x",
        login_mode="demo",
    )
    assert any(s.get("action") == "navigate_app" and s.get("path") == R.DASHBOARD for s in steps)
    assert any(s.get("action") == "wait_for_module" for s in steps)


def test_portfolio_tabs_include_holdings():
    steps = build_profile_steps(
        "PORTFOLIO_TABS_FLOW",
        target_url="http://localhost:9000",
        email="a@b.com",
        password="x",
        login_mode="demo",
    )
    assert any("holdings" in str(s.get("path", "")) for s in steps)


def test_market_smoke_visits_all_indices():
    steps = build_profile_steps(
        "MARKET_SMOKE_FLOW",
        target_url="http://localhost:9000",
        email="a@b.com",
        password="x",
        login_mode="demo",
    )
    assert any("all-indices" in str(s.get("path", "")) for s in steps)


def test_trade_and_doc_profiles():
    trade = build_profile_steps(
        "TRADE_SMOKE_FLOW",
        target_url="http://localhost:9000",
        email="a",
        password="b",
    )
    doc = build_profile_steps(
        "DOC_INTEL_SMOKE_FLOW",
        target_url="http://localhost:9000",
        email="a",
        password="b",
    )
    assert any(R.TRADE_DISCOVERY in str(s.get("path", "")) for s in trade)
    assert any("doc-processor" in str(s.get("path", "")) for s in doc)


def test_admin_gate_redirects_lab():
    steps = build_profile_steps(
        "ADMIN_GATE_FLOW",
        target_url="http://localhost:9000",
        email="a",
        password="b",
        expect_admin=False,
    )
    assert any(s.get("path") == R.LAB for s in steps)
    assert any(
        s.get("action") == "assert_url_contains" and s.get("pattern") == R.DASHBOARD
        for s in steps
    )


def test_routes_helpers():
    assert R.app_url("http://localhost:9000", R.DASHBOARD).endswith("/app/dashboard")
    assert R.portfolio_path("abc", "holdings") == "/app/portfolio/abc/holdings"
    assert R.market_path() == "/app/market/all-indices"


import pytest

from app.agent import planner as planner_mod
from app.config import Settings


@pytest.mark.asyncio
async def test_planner_uses_deterministic_profile_without_llm(monkeypatch):
    cfg = Settings(
        LLM_ROUTING="direct",
        APP_ENV="preprod",
        LITELLM_MASTER_KEY="sk-test",
        AUTH_LOGIN_MODE="demo",
    )
    monkeypatch.setattr(planner_mod, "settings", cfg)

    class FakeCtx:
        profile = "PORTFOLIO_SMOKE_FLOW"
        session_id = "s1"
        test_id = "t1"

        class llm_client:
            @staticmethod
            async def chat_text(**kwargs):
                raise AssertionError("LLM should not be called for deterministic profile")

    steps = await planner_mod.plan_steps(
        target_url="http://localhost:9000",
        specification="",
        profile="PORTFOLIO_SMOKE_FLOW",
        ctx=FakeCtx(),
    )
    assert len(steps) >= 8
    assert any(s["action"] == "navigate_app" for s in steps)
