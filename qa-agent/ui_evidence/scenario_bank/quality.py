"""Auto quality rating for invent bank (stored in qa_knowledge)."""
from __future__ import annotations

from typing import Any

from ui_evidence.scenario_bank.repo import get_repo, norm_env
from ui_evidence.scenario_bank.scenario_planner import load_invent_skill_ids


def rate_invent_bank(service_key: str, env: str) -> dict[str, Any]:
    """Score 1–10 from skill coverage, runnable ratio, surface use, schema completeness."""
    env_n = norm_env(env)
    repo = get_repo()
    scenarios = [
        s
        for s in repo.list_scenarios(service_key, env_n)
        if s.get("llm_invented") or (not s.get("seed"))
    ]
    # Prefer llm rows for scoring; if none, use all non-empty-step rows
    invent_rows = [s for s in scenarios if s.get("llm_invented")]
    rows = invent_rows or [
        s for s in repo.list_scenarios(service_key, env_n) if s.get("steps")
    ]
    skills_wanted = set(load_invent_skill_ids())
    skills_have = {str(s.get("skill")) for s in rows if s.get("skill")}
    skill_coverage = (
        len(skills_have & skills_wanted) / max(1, len(skills_wanted))
    )
    runnable = sum(1 for s in rows if s.get("status") == "runnable")
    runnable_ratio = runnable / max(1, len(rows))

    surface = repo.get_surface(service_key, env_n)
    surface_paths = {
        str(t.get("path") or "").lower()
        for t in (surface.get("tools") or [])
        if t.get("path")
    }
    used_paths: set[str] = set()
    schema_ok = 0
    for s in rows:
        steps = s.get("steps") or []
        has_status = True
        for st in steps:
            if not isinstance(st, dict):
                has_status = False
                continue
            p = str(st.get("path") or "").lower()
            if p:
                used_paths.add(p)
            if st.get("expected_status") is None:
                has_status = False
        if has_status and steps and s.get("auth") is not None:
            schema_ok += 1
    schema_ratio = schema_ok / max(1, len(rows))
    surface_coverage = len(used_paths & surface_paths) / max(1, len(surface_paths)) if surface_paths else 0.0

    # Weighted score
    raw = (
        0.35 * skill_coverage
        + 0.30 * runnable_ratio
        + 0.20 * schema_ratio
        + 0.15 * min(1.0, surface_coverage * 3)  # partial surface use is fine
    )
    score = round(1 + raw * 9, 1)  # 1.0 .. 10.0
    reasons: list[str] = []
    if skill_coverage < 0.7:
        missing = sorted(skills_wanted - skills_have)
        reasons.append(f"skill_coverage={skill_coverage:.0%} missing={missing[:5]}")
    else:
        reasons.append(f"skill_coverage={skill_coverage:.0%}")
    reasons.append(f"runnable_ratio={runnable_ratio:.0%} ({runnable}/{len(rows)})")
    reasons.append(f"schema_v2_ratio={schema_ratio:.0%}")
    reasons.append(f"surface_path_use={len(used_paths & surface_paths)}/{len(surface_paths)}")
    if not surface_paths:
        reasons.append("no_api_surface_in_db")
        score = min(score, 5.0)

    result = {
        "ok": True,
        "service_key": service_key,
        "env": env_n,
        "quality_score": score,
        "quality_reasons": reasons,
        "skill_coverage": round(skill_coverage, 3),
        "runnable_ratio": round(runnable_ratio, 3),
        "schema_ratio": round(schema_ratio, 3),
        "surface_coverage": round(surface_coverage, 3),
        "invent_row_count": len(rows),
        "skills_present": sorted(skills_have),
    }
    repo.upsert_knowledge(
        service_key,
        env_n,
        {
            "quality_score": score,
            "quality_reasons": reasons,
            "skill_coverage": result["skill_coverage"],
            "runnable_ratio": result["runnable_ratio"],
            "schema_ratio": result["schema_ratio"],
            "surface_coverage": result["surface_coverage"],
            "invent_row_count": len(rows),
        },
    )
    # keep invent flags on meta
    meta = repo.get_meta(service_key, env_n)
    result["invent_complete"] = bool(meta.get("invent_complete"))
    return result
