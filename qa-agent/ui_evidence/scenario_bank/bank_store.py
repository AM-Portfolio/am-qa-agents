"""Scenario bank store — Mongo SoT via repo (memory backend for tests)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from ui_evidence.scenario_bank.repo import get_repo, norm_env, reset_repo_for_tests

logger = logging.getLogger(__name__)

BANK_CAP = 200
LOCK_TTL_SECONDS = 300

# Re-export for tests that reset isolation
__all__ = [
    "BANK_CAP",
    "LOCK_TTL_SECONDS",
    "load_bank",
    "list_scenarios",
    "upsert_scenario",
    "clear_llm_invented",
    "set_flags",
    "seed_default_rows",
    "acquire_invent_lock",
    "release_invent_lock",
    "reset_repo_for_tests",
]


def load_bank(service_key: str, env: str) -> dict[str, Any]:
    env_n = norm_env(env)
    repo = get_repo()
    meta = repo.get_meta(service_key, env_n)
    scenarios = repo.list_scenarios(service_key, env_n)
    return {
        "service_key": service_key,
        "env": env_n,
        "invent_complete": bool(meta.get("invent_complete")),
        "needs_reinvent": bool(meta.get("needs_reinvent")),
        "scenarios": scenarios,
        "updated_at": meta.get("updated_at"),
        "backend": getattr(repo, "__class__", type(repo)).__name__,
    }


def list_scenarios(service_key: str, env: str) -> list[dict[str, Any]]:
    return get_repo().list_scenarios(service_key, env)


def upsert_scenario(
    service_key: str,
    env: str,
    row: dict[str, Any],
    *,
    cap: int = BANK_CAP,
) -> dict[str, Any]:
    return get_repo().upsert_scenario(service_key, env, row, cap=cap)


def clear_llm_invented(service_key: str, env: str) -> dict[str, Any]:
    return get_repo().clear_llm_invented(service_key, env)


def set_flags(
    service_key: str,
    env: str,
    *,
    invent_complete: Optional[bool] = None,
    needs_reinvent: Optional[bool] = None,
) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if invent_complete is not None:
        patch["invent_complete"] = bool(invent_complete)
    if needs_reinvent is not None:
        patch["needs_reinvent"] = bool(needs_reinvent)
    meta = get_repo().set_meta(service_key, env, patch) if patch else get_repo().get_meta(
        service_key, env
    )
    return {
        "ok": True,
        "invent_complete": meta.get("invent_complete"),
        "needs_reinvent": meta.get("needs_reinvent"),
    }


def seed_default_rows(service_key: str, env: str, skills: list[str]) -> dict[str, Any]:
    upserted = []
    for skill in skills:
        r = upsert_scenario(
            service_key,
            env,
            {
                "skill": skill,
                "kind": "api",
                "status": "runnable" if skill == "data_generator" else "draft",
                "seed": True,
                "steps": [],
                "prep_needs": ["data_generator"] if skill != "data_generator" else [],
                "dedupe_key": f"seed:{skill}",
            },
        )
        upserted.append(r)
    return {
        "ok": True,
        "seeded": len(upserted),
        "count": len(list_scenarios(service_key, env)),
    }


def acquire_invent_lock(
    service_key: str,
    env: str,
    *,
    owner: str = "",
    ttl: int = LOCK_TTL_SECONDS,
) -> dict[str, Any]:
    return get_repo().acquire_lock(service_key, env, owner=owner, ttl=ttl)


def release_invent_lock(service_key: str, env: str, *, owner: str) -> dict[str, Any]:
    return get_repo().release_lock(service_key, env, owner=owner)
