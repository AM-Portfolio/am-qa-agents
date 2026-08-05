from ui_evidence.profiles.registry import (
    DETERMINISTIC_PROFILES,
    PROD_UI_FULL_PROFILES,
    RELEASE_GATE_PROFILES,
    build_profile_steps,
    is_deterministic_profile,
    suite_profiles,
)
from ui_evidence.profiles.modern_ui import routes as R
from ui_evidence.profiles.modern_ui.auth_flow import build_auth_flow_steps, detect_ui_mode


def test_auth_profiles_still_deterministic():
    assert is_deterministic_profile("AUTH_FLOW_MAIN")
    assert is_deterministic_profile("PORTFOLIO_SMOKE_FLOW")
    assert "DASHBOARD_SMOKE_FLOW" in DETERMINISTIC_PROFILES


def test_release_gate_profiles():
    assert "AUTH_FLOW_MAIN" in RELEASE_GATE_PROFILES
    assert "PORTFOLIO_SMOKE_FLOW" in RELEASE_GATE_PROFILES
    assert "MARKET_USER_FLOW" in RELEASE_GATE_PROFILES


def test_prod_ui_full_suite():
    profiles = suite_profiles("prod_ui_full")
    assert "PORTFOLIO_TABS_FLOW" in profiles
    assert "TRADE_TABS_FLOW" in profiles
    assert "MARKET_USER_FLOW" in profiles
    assert "MARKET_GATE_FLOW" in profiles
    assert "DOC_UPLOAD_FLOW" not in profiles
    assert profiles == PROD_UI_FULL_PROFILES


def test_live_portfolio_tabs_exclude_orphan_analysis():
    assert "analysis" not in R.PORTFOLIO_TABS
    assert R.PORTFOLIO_TABS == ("overview", "holdings", "heatmap", "baskets")


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


def test_portfolio_tabs_include_holdings_and_heatmap():
    steps = build_profile_steps(
        "PORTFOLIO_TABS_FLOW",
        target_url="http://localhost:9000",
        email="a@b.com",
        password="x",
        login_mode="demo",
        portfolio_id="p1",
    )
    paths = [str(s.get("path", "")) for s in steps]
    assert any("holdings" in p for p in paths)
    assert any("heatmap" in p for p in paths)
    assert any("baskets" in p for p in paths)
    assert not any("/analysis" in p for p in paths)


def test_market_user_visits_dashboard():
    steps = build_profile_steps(
        "MARKET_USER_FLOW",
        target_url="http://localhost:9000",
        email="a@b.com",
        password="x",
        login_mode="demo",
    )
    paths = [str(s.get("path", "")) for s in steps]
    assert any("dashboard" in p for p in paths)
    assert any("market-analysis" in p for p in paths)
    assert not any("all-indices" in p for p in paths)


def test_market_smoke_aliases_user_flow():
    steps = build_profile_steps(
        "MARKET_SMOKE_FLOW",
        target_url="http://localhost:9000",
        email="a@b.com",
        password="x",
        login_mode="demo",
    )
    assert any("dashboard" in str(s.get("path", "")) for s in steps)


def test_market_dev_skips_admin_tools():
    steps = build_profile_steps(
        "MARKET_DEV_FLOW",
        target_url="http://localhost:9000",
        email="a@b.com",
        password="x",
        login_mode="credentials",
    )
    paths = [str(s.get("path", "")) for s in steps]
    assert any("all-indices" in p for p in paths)
    assert any("instrument-explorer" in p for p in paths)
    assert not any("/admin" in p for p in paths)
    assert not any("price-test" in p for p in paths)


def test_market_gate_redirects_admin():
    steps = build_profile_steps(
        "MARKET_GATE_FLOW",
        target_url="http://localhost:9000",
        email="a",
        password="b",
    )
    assert any(s.get("path") == R.market_path("admin") for s in steps)
    assert any(
        s.get("action") == "assert_url_contains" and s.get("pattern") == "dashboard"
        for s in steps
    )


def test_trade_tabs_sweep_all_view_tabs():
    steps = build_profile_steps(
        "TRADE_TABS_FLOW",
        target_url="http://localhost:9000",
        email="a",
        password="b",
        portfolio_id="p1",
    )
    paths = [str(s.get("path", "")) for s in steps]
    for tab in ("holdings", "calendar", "trades", "journal", "analysis", "report", "templates"):
        assert any(tab in p for p in paths), tab


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
    assert R.market_path() == "/app/market/dashboard"


import pytest

from ui_evidence.agent import planner as planner_mod
from ui_evidence.config import Settings


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
