"""HITL RBAC — role-based approve.release."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _allowed_roles() -> set[str]:
    env = os.getenv("QA_AGENT_HITL_ROLES", "")
    if env:
        return {r.strip() for r in env.split(",") if r.strip()}
    cfg = Path(__file__).resolve().parents[3] / "config" / "release-policy.yaml"
    if cfg.is_file():
        with open(cfg, encoding="utf-8") as f:
            roles = ((yaml.safe_load(f) or {}).get("hitl") or {}).get("roles") or []
            return {str(r) for r in roles}
    return {"release-approver"}


def authorize_hitl_actor(actor: str, roles: list[str] | None = None) -> dict[str, Any]:
    """
    Authorize HITL signal actor.

    Bypass when QA_AGENT_HITL_RBAC=false (local default) or actor is 'auto'.
    """
    if os.getenv("QA_AGENT_HITL_RBAC", "false").lower() not in {"1", "true", "yes"}:
        return {"allowed": True, "mode": "rbac_disabled", "actor": actor}
    if actor in {"auto", "system"}:
        return {"allowed": True, "mode": "system", "actor": actor}
    allowed = _allowed_roles()
    provided = set(roles or [])
    if actor in allowed or provided & allowed:
        return {
            "allowed": True,
            "mode": "role_match",
            "actor": actor,
            "roles": list(provided or [actor]),
        }
    if "@" in actor and actor.split("@", 1)[1] in allowed:
        return {"allowed": True, "mode": "actor_role_suffix", "actor": actor}
    return {
        "allowed": False,
        "mode": "denied",
        "actor": actor,
        "required_roles": sorted(allowed),
        "provided_roles": sorted(provided),
    }
