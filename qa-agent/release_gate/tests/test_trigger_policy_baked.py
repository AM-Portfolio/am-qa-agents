"""Policy file includes first-cut product allowlist."""

from __future__ import annotations

from intelligence.trigger_policy import evaluate_ci_merge, load_trigger_policy


def test_baked_policy_allows_core_analysis() -> None:
    pol = load_trigger_policy()
    ok, reason = evaluate_ci_merge(
        repo="AM-Portfolio/am-core-services",
        branch="main",
        service="am-analysis",
        policy=pol,
    )
    assert ok is True, reason
    assert reason == "ok"


def test_baked_policy_allows_modern_ui() -> None:
    pol = load_trigger_policy()
    ok, reason = evaluate_ci_merge(
        repo="am-modern-ui",
        branch="main",
        service="am-modern-ui",
        policy=pol,
    )
    assert ok is True, reason


def test_baked_policy_denies_unknown_service() -> None:
    pol = load_trigger_policy()
    ok, reason = evaluate_ci_merge(
        repo="am-core-services",
        branch="main",
        service="am-unknown",
        policy=pol,
    )
    assert ok is False
    assert "service_not_allowed" in reason
