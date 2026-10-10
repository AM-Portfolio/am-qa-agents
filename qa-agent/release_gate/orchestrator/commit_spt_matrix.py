"""Branch → SPT matrix for CommitSptWorkflow (am-market-data pilot)."""

from __future__ import annotations

from typing import Any


def resolve_commit_spt_matrix(git_ref: str) -> dict[str, Any]:
    """Map git branch to dataset_profile / intensity / fail semantics."""
    ref = (git_ref or "").strip()
    if ref.startswith("refs/heads/"):
        ref = ref[len("refs/heads/") :]
    lower = ref.lower()

    def smoke(triggered: str, *, fail: bool = False) -> dict[str, Any]:
        return {
            "dataset_profile": "working",
            "profile": "debug",
            "preset": "ci-smoke",
            "vus": 1,
            "iterations": 1,
            "triggered_by": triggered,
            "fail_on_unexpected": fail,
            "matrix_label": "working+debug 1x1",
        }

    if lower in {"main", "master"}:
        return {
            "dataset_profile": "full",
            "profile": "load",
            "preset": "ci-load",
            "vus": 10,
            "iterations": 100,
            "triggered_by": "ci-main",
            "fail_on_unexpected": True,
            "matrix_label": "full+load ramp+100iters",
        }
    if lower in {"develop", "dev"}:
        return smoke("ci-develop", fail=True)
    for prefix in ("feature/", "fix/", "hotfix/", "test/"):
        if lower.startswith(prefix):
            return smoke(f"ci-{prefix.rstrip('/')}", fail=False)
    return smoke("ci-branch", fail=False)


def push_touches_market_data(payload: dict[str, Any]) -> bool:
    """True when a GitHub push event touches am-market-data/**."""
    for commit in payload.get("commits") or []:
        if not isinstance(commit, dict):
            continue
        for key in ("added", "modified", "removed"):
            for path in commit.get(key) or []:
                if str(path).startswith("am-market-data/"):
                    return True
    # Force-push / empty commits: look at head_commit
    hc = payload.get("head_commit") or {}
    for key in ("added", "modified", "removed"):
        for path in hc.get(key) or []:
            if str(path).startswith("am-market-data/"):
                return True
    return False
