"""Tests for CI merge trigger policy (am-analysis pilot)."""

from __future__ import annotations

from intelligence.trigger_policy import evaluate_ci_merge


PILOT = {
    "default": "deny",
    "repos": [
        {
            "name": "am-core-services",
            "branches": ["master", "main"],
            "services": ["am-analysis"],
        }
    ],
}


def test_allows_pilot_core_analysis_on_master() -> None:
    ok, reason = evaluate_ci_merge(
        repo="ssd2658/am-core-services",
        branch="master",
        service="am-analysis",
        policy=PILOT,
    )
    assert ok is True
    assert reason == "ok"


def test_denies_missing_service() -> None:
    ok, reason = evaluate_ci_merge(
        repo="am-core-services",
        branch="master",
        service=None,
        policy=PILOT,
    )
    assert ok is False
    assert reason == "service_required"


def test_denies_other_service() -> None:
    ok, reason = evaluate_ci_merge(
        repo="am-core-services",
        branch="master",
        service="am-gateway",
        policy=PILOT,
    )
    assert ok is False
    assert "service_not_allowed" in reason


def test_denies_other_repo() -> None:
    ok, reason = evaluate_ci_merge(
        repo="am-portfolio",
        branch="main",
        service="am-analysis",
        policy=PILOT,
    )
    assert ok is False
    assert "repo_not_in_policy" in reason


def test_denies_wrong_branch() -> None:
    ok, reason = evaluate_ci_merge(
        repo="am-core-services",
        branch="feature/x",
        service="am-analysis",
        policy=PILOT,
    )
    assert ok is False
    assert "branch_not_allowed" in reason
