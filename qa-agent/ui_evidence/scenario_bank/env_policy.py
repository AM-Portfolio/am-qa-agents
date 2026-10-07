"""Env filter for scenario bank select (Phase 6). Contabo prod blocks L5/security."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_BLOCKED_CONTABO = frozenset({"level5_abuse", "security"})
_SKIP_MUTATE_CONTABO = frozenset(
    {
        "level3_edge",
        "null_point",
        "tweak_data",
        "level4_state",
    }
)


def normalize_env(env: str) -> str:
    e = (env or "dev").strip().lower()
    if e == "dig":
        return "dev"
    if e in {"contabo_prod", "contabo", "production"}:
        return "prod"
    return e


def _skills_env_map() -> dict[str, dict[str, str]]:
    path = Path(__file__).resolve().parent / "skills.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, dict[str, str]] = {}
    for row in data.get("skills") or []:
        sid = str(row.get("id") or "")
        if not sid:
            continue
        env = row.get("env") or {}
        if isinstance(env, dict):
            out[sid] = {str(k).lower(): str(v).lower() for k, v in env.items()}
    return out


def skill_action(skill: str, env: str) -> str:
    """Return run | block | skip | skip_mutate | read_only | assert_only."""
    env_n = normalize_env(env)
    mapping = _skills_env_map().get(skill) or {}
    if env_n == "prod":
        # skills.yaml uses contabo_prod key
        action = mapping.get("contabo_prod") or mapping.get("prod") or "run"
    else:
        action = mapping.get("dev") or mapping.get(env_n) or "run"
    # Hard blocks regardless of yaml typos
    if env_n == "prod" and skill in _BLOCKED_CONTABO:
        return "block"
    return action


def filter_scenarios_for_env(
    scenarios: list[dict[str, Any]],
    env: str,
) -> dict[str, Any]:
    """Split scenarios into selected vs skipped for env policy."""
    env_n = normalize_env(env)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in scenarios:
        skill = str(row.get("skill") or "")
        action = skill_action(skill, env_n)
        status = str(row.get("status") or "")
        if action in {"block", "skip"}:
            skipped.append({**row, "skip_reason": action})
            continue
        if env_n == "prod" and skill in _SKIP_MUTATE_CONTABO and action == "skip_mutate":
            skipped.append({**row, "skip_reason": "skip_mutate"})
            continue
        if status in {"draft", "draft_ui"}:
            skipped.append({**row, "skip_reason": "not_runnable"})
            continue
        selected.append({**row, "env_action": action})
    return {
        "env": env_n,
        "selected": selected,
        "skipped": skipped,
        "selected_count": len(selected),
        "skipped_count": len(skipped),
    }


def select_few(
    scenarios: list[dict[str, Any]],
    env: str,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Env-filter then pick prefer mix from skills.yaml."""
    path = Path(__file__).resolve().parent / "skills.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mix = [str(x) for x in (data.get("select_few_mix") or [])]
    default_n = int(data.get("select_few_default") or 6)
    n = default_n if limit is None else int(limit)

    filtered = filter_scenarios_for_env(scenarios, env)
    pool = list(filtered["selected"])
    by_skill: dict[str, list[dict[str, Any]]] = {}
    for row in pool:
        by_skill.setdefault(str(row.get("skill") or ""), []).append(row)

    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for skill in mix:
        if skill == "never_run_or_failed":
            continue
        for row in by_skill.get(skill) or []:
            key = str(row.get("dedupe_key") or row.get("id") or "")
            if key in seen:
                continue
            picked.append(row)
            seen.add(key)
            break
        if len(picked) >= n:
            break
    if len(picked) < n:
        for row in pool:
            key = str(row.get("dedupe_key") or row.get("id") or "")
            if key in seen:
                continue
            picked.append(row)
            seen.add(key)
            if len(picked) >= n:
                break

    return {
        **filtered,
        "select_few": picked,
        "select_few_count": len(picked),
        "limit": n,
    }
