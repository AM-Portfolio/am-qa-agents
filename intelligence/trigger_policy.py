"""CI merge allowlist — opt-in repos/services for trigger_kind=ci_master_merge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _config_dir() -> Path:
    env = os.getenv("QA_AGENT_CONFIG_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "config"


def load_trigger_policy() -> dict[str, Any]:
    path = _config_dir() / "trigger-policy.yaml"
    if not path.is_file():
        return {"default": "allow", "repos": []}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _short_repo(repo: str) -> str:
    return repo.split("/")[-1] if repo else ""


def evaluate_ci_merge(
    *,
    repo: str,
    branch: str,
    service: str | None = None,
    policy: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Return (allowed, reason). Only apply when caller has trigger_kind=ci_master_merge."""
    doc = policy if policy is not None else load_trigger_policy()
    default = str(doc.get("default") or "deny").lower()
    entries = doc.get("repos") or []
    short = _short_repo(repo)
    match: dict[str, Any] | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        if name in {repo, short}:
            match = entry
            break

    if match is None:
        if default == "allow":
            return True, "default_allow"
        return False, f"repo_not_in_policy:{short or repo}"

    branches = match.get("branches") or []
    if branches and branch not in branches:
        return False, f"branch_not_allowed:{branch}"

    services = match.get("services") or []
    if services:
        if not service:
            return False, "service_required"
        if service not in services:
            return False, f"service_not_allowed:{service}"

    return True, "ok"
