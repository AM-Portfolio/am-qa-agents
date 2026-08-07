from datetime import datetime

from ui_evidence.browser.evidence_paths import (
    evidence_run_dirname,
    profile_evidence_prefix,
    slugify_step_name,
    step_screenshot_filename,
)


def test_profile_evidence_prefix_auth():
    assert profile_evidence_prefix("AUTH_FLOW_MAIN") == "auth"
    assert profile_evidence_prefix("AUTH_FLOW_PORTFOLIO") == "auth"


def test_profile_evidence_prefix_domains():
    assert profile_evidence_prefix("PORTFOLIO_SMOKE_FLOW") == "portfolio"
    assert profile_evidence_prefix("TRADE_TABS_FLOW") == "trade"
    assert profile_evidence_prefix("MARKET_USER_FLOW") == "market"


def test_evidence_run_dirname_includes_prefix_and_stamp():
    when = datetime(2026, 8, 6, 11, 9, 30)
    name = evidence_run_dirname(
        "AUTH_FLOW_MAIN",
        "0f899509-053f-4b11-807e-7561885e9fdc",
        when,
    )
    assert name == "auth-20260806-110930-0f899509"


def test_step_screenshot_filename_readable():
    when = datetime(2026, 8, 6, 11, 10, 5)
    name = step_screenshot_filename(
        3,
        step_name="3. Screenshot — login form visible",
        when=when,
    )
    assert name == "003-111005-login-form-visible.png"


def test_slugify_strips_screenshot_prefix():
    assert slugify_step_name("6. Screenshot — credentials entered") == "credentials-entered"
