"""Tests for CI merge trigger policy (inline policy fixtures — not baked product names)."""

from __future__ import annotations

from intelligence.trigger_policy import evaluate_ci_merge


SAMPLE = {
    "default": "deny",
    "repos": [
        {
            "name": "example-monorepo",
            "branches": ["master", "main"],
            "services": ["demo-service"],
        }
    ],
}


def test_allows_listed_service_on_master() -> None:
    ok, reason = evaluate_ci_merge(
        repo="org/example-monorepo",
        branch="master",
        service="demo-service",
        policy=SAMPLE,
    )
    assert ok is True
    assert reason == "ok"


def test_denies_missing_service() -> None:
    ok, reason = evaluate_ci_merge(
        repo="example-monorepo",
        branch="master",
        service=None,
        policy=SAMPLE,
    )
    assert ok is False
    assert reason == "service_required"


def test_denies_other_service() -> None:
    ok, reason = evaluate_ci_merge(
        repo="example-monorepo",
        branch="master",
        service="other-service",
        policy=SAMPLE,
    )
    assert ok is False
    assert "service_not_allowed" in reason


def test_denies_other_repo() -> None:
    ok, reason = evaluate_ci_merge(
        repo="other-repo",
        branch="main",
        service="demo-service",
        policy=SAMPLE,
    )
    assert ok is False
    assert "repo_not_in_policy" in reason


def test_denies_wrong_branch() -> None:
    ok, reason = evaluate_ci_merge(
        repo="example-monorepo",
        branch="feature/x",
        service="demo-service",
        policy=SAMPLE,
    )
    assert ok is False
    assert "branch_not_allowed" in reason
