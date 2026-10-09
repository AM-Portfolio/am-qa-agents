"""Resolve data-gen suite + env from git ref / branch name."""
from __future__ import annotations

from typing import Any


def _normalize_ref(ref: str | None) -> str:
    raw = (ref or "").strip()
    if raw.startswith("refs/heads/"):
        raw = raw[len("refs/heads/") :]
    if raw.startswith("refs/tags/"):
        raw = raw[len("refs/tags/") :]
    return raw.strip().lower()


def resolve_data_gen_profile(ref: str | None = None, *, explicit: str | None = None) -> str:
    """Always suite ``default`` for develop/hotfix/main; explicit wins when set.

    ``full`` / ``premium`` never come from branch alone.
    """
    if explicit and str(explicit).strip():
        e = str(explicit).strip().lower()
        if e in {"default", "working", "full", "premium", "prod"}:
            return "default" if e in {"working", "prod"} else e
        return e
    # Branch families all map to default (plan 2b)
    _ = _normalize_ref(ref)
    return "default"


def resolve_data_gen_environment(
    ref: str | None = None,
    *,
    explicit: str | None = None,
) -> str:
    """Branch → env hint: develop→dev, hotfix/main→preprod. Never silent prod."""
    if explicit and str(explicit).strip():
        e = str(explicit).strip().lower()
        return "dev" if e == "dig" else e
    branch = _normalize_ref(ref)
    if not branch:
        return "dev"
    if branch in {"main", "master"} or branch.startswith("hotfix/") or branch == "hotfix":
        return "preprod"
    if branch in {"develop", "dev", "dig"} or branch.startswith(
        ("feature/", "fix/", "feat/")
    ):
        return "dev"
    return "dev"


def resolve_branch_defaults(
    *,
    git_ref: str | None = None,
    profile: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    suite = resolve_data_gen_profile(git_ref, explicit=profile)
    env = resolve_data_gen_environment(git_ref, explicit=environment)
    return {
        "suite": suite,
        "profile": suite,  # disk profile resolved later via SUITE_TO_PROFILE
        "environment": env,
        "git_ref": git_ref,
        "from_branch": not bool(profile and str(profile).strip()),
    }
