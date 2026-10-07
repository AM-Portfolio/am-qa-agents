"""Build invent context packs from typed prompts + DB-derived service profile/surface."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from prompts.loader import PromptBundle, load_prompt_type
from ui_evidence.scenario_bank.repo import get_repo, norm_env

CONTEXT_BUDGET = 14000


def ban_patterns(bundle: Optional[PromptBundle] = None) -> list[re.Pattern[str]]:
    bans = (bundle.bans if bundle else {}) or {}
    pats: list[re.Pattern[str]] = []
    for s in bans.get("path_substrings") or []:
        pats.append(re.compile(re.escape(str(s)), re.IGNORECASE))
    for s in bans.get("regex") or []:
        try:
            pats.append(re.compile(str(s)))
        except re.error:
            continue
    return pats


def path_is_banned(path: str, patterns: list[re.Pattern[str]]) -> bool:
    p = path or ""
    return any(rx.search(p) for rx in patterns)


def yaml_dump_bans(bans: dict[str, Any]) -> str:
    if not bans:
        return ""
    lines: list[str] = []
    for s in bans.get("path_substrings") or []:
        lines.append(f"- substring: {s}")
    for s in bans.get("regex") or []:
        lines.append(f"- regex: {s}")
    return "\n".join(lines)


def build_api_surface(tools: list[dict[str, Any]], *, limit: int = 120) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for t in tools:
        method = str(t.get("method") or "").upper()
        path = str(t.get("path") or t.get("operation_path") or "")
        if not path:
            continue
        title = str(t.get("title") or t.get("name") or "").strip()
        key = f"{method} {path}"
        if key in seen:
            continue
        seen.add(key)
        suffix = f"  # {title}" if title else ""
        lines.append(f"{key}{suffix}")
        if len(lines) >= limit:
            break
    return lines


def path_sequence_fingerprint(steps: list[Any]) -> str:
    parts: list[str] = []
    for st in steps or []:
        if not isinstance(st, dict):
            continue
        m = str(st.get("method") or "get").lower()
        p = str(st.get("path") or st.get("operation_path") or "").lower()
        parts.append(f"{m}:{p}")
    return "|".join(parts)


def existing_fingerprints(scenarios: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    keys: list[str] = []
    fps: list[str] = []
    for row in scenarios or []:
        dk = str(row.get("dedupe_key") or "")
        if dk:
            keys.append(dk)
        fp = path_sequence_fingerprint(list(row.get("steps") or []))
        if fp:
            fps.append(fp)
    return keys[:80], fps[:80]


def format_service_profile(profile: dict[str, Any], service_key: str) -> str:
    if not profile:
        return (
            f"service_key: {service_key}\n"
            "(no invent profile in DB yet — derive from tools first)"
        )
    lines = [
        f"service_key: {profile.get('service_key') or service_key}",
        f"derived: {profile.get('derived', False)}",
        f"default_auth: {profile.get('default_auth') or 'user_jwt'}",
        "domain:",
        str(profile.get("domain") or "").strip(),
    ]
    for key in (
        "auth_modes",
        "entities",
        "primary_reads",
        "protected_paths",
        "mutate_paths",
        "null_ids",
        "lifecycle",
        "notes",
    ):
        val = profile.get(key)
        if not val:
            continue
        lines.append(f"{key}:")
        if isinstance(val, list):
            for item in val:
                lines.append(f"  - {item}")
        else:
            lines.append(f"  {val}")
    if profile.get("observe_after_mutate"):
        lines.append(f"observe_after_mutate: {profile['observe_after_mutate']}")
    return "\n".join(lines).strip()


def format_skill_overlays(profile: dict[str, Any], skill_ids: list[str]) -> str:
    overlays = profile.get("skill_overlays") or {}
    if not isinstance(overlays, dict) or not overlays:
        return "(no skill_overlays in DB profile — use platform Diversity hints + api_surface)"
    blocks: list[str] = []
    for sid in skill_ids:
        ov = overlays.get(sid)
        if not isinstance(ov, dict):
            continue
        diversify = ov.get("diversify") or []
        lines = [f"### skill_overlay: {sid}"]
        if diversify:
            lines.append("diversify:")
            for d in diversify:
                lines.append(f"  - {d}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) if blocks else "(no overlays for this skill chunk)"


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def render_user_prompt(
    template: str,
    *,
    service: str,
    env: str,
    skills: list[str],
    scenarios_per_skill: int,
    schema_version: str,
    playbooks: str,
    skill_overlays: str,
    service_profile: str,
    api_surface: str,
    bans: str,
    catalog: str,
    existing: str,
) -> str:
    repl = {
        "{{service}}": service,
        "{{env}}": env,
        "{{skills_json}}": json.dumps(skills),
        "{{scenarios_per_skill}}": str(scenarios_per_skill),
        "{{schema_version}}": schema_version,
        "{{playbooks}}": playbooks,
        "{{skill_overlays}}": skill_overlays,
        "{{service_profile}}": service_profile,
        "{{api_surface}}": api_surface,
        "{{bans}}": bans,
        "{{catalog}}": catalog,
        "{{existing}}": existing,
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def render_chunk_user(
    pack: dict[str, Any],
    *,
    service_key: str,
    env: str,
    chunk_skills: list[str],
    scenarios_per_skill: int,
) -> str:
    bundle: PromptBundle = pack["bundle"]
    playbook_text = "\n\n".join(
        bundle.playbooks[sid] for sid in chunk_skills if sid in bundle.playbooks
    )
    profile = pack.get("service_profile_data") or {}
    overlays = format_skill_overlays(profile, chunk_skills)
    return render_user_prompt(
        bundle.user_template,
        service=service_key,
        env=env,
        skills=chunk_skills,
        scenarios_per_skill=scenarios_per_skill,
        schema_version=bundle.schema_version,
        playbooks=_truncate(playbook_text, 4500) or "(none)",
        skill_overlays=_truncate(overlays, 2500),
        service_profile=str(pack.get("service_profile_text") or "(none)"),
        api_surface=str(pack.get("api_surface_text") or "(empty)"),
        bans=str(pack.get("bans_text") or "(none)"),
        catalog=str(pack.get("catalog_text") or "(none)"),
        existing=str(pack.get("existing_text") or "(none)"),
    )


def build_invent_pack(
    service_key: str,
    env: str,
    *,
    tools: list[dict[str, Any]],
    skill_ids: list[str],
    existing_scenarios: Optional[list[dict[str, Any]]] = None,
    plugin_root: Optional[Path] = None,
    scenarios_per_skill: int = 2,
    budget: int = CONTEXT_BUDGET,
) -> dict[str, Any]:
    """
    Load type=invent + DB profile/surface (derive if missing).
    plugin_root is ignored for invent SoT (kept for call-compat).
    """
    del plugin_root  # invent SoT is DB, not plugin catalog files
    env_n = norm_env(env)
    repo = get_repo()
    bundle = load_prompt_type("invent", skill_ids=skill_ids, require_playbooks=True)
    patterns = ban_patterns(bundle)

    surface_doc = repo.get_surface(service_key, env_n)
    profile = repo.get_profile(service_key, env_n)
    if not surface_doc.get("lines") and tools:
        from ui_evidence.scenario_bank.spec_derive import derive_and_store

        derived = derive_and_store(service_key, env_n, tools)
        surface_doc = derived.get("surface") or repo.get_surface(service_key, env_n)
        profile = derived.get("profile") or repo.get_profile(service_key, env_n)

    surface_lines = list(surface_doc.get("lines") or [])
    if not surface_lines:
        surface_lines = [
            ln
            for ln in build_api_surface(tools)
            if not path_is_banned(ln.split("  #")[0], patterns)
        ]
    else:
        surface_lines = [
            ln
            for ln in surface_lines
            if not path_is_banned(ln.split("  #")[0], patterns)
        ]

    surface_text = _truncate(
        "\n".join(surface_lines) or "(empty)", min(5500, budget // 2)
    )
    ban_text = yaml_dump_bans(bundle.bans)
    service_profile_text = format_service_profile(profile, service_key)
    # catalogs no longer from plugin files — brief from DB profile notes
    catalog = "source: qa_invent_profiles + qa_api_surface (DB)\n" + "\n".join(
        f"- {n}" for n in (profile.get("notes") or [])[:6]
    )
    keys, fps = existing_fingerprints(list(existing_scenarios or []))
    existing_text = "dedupe_keys:\n" + "\n".join(keys[:40] or ["(none)"])
    if fps:
        existing_text += "\npath_fingerprints:\n" + "\n".join(fps[:40])

    remain = max(2000, budget - len(surface_text) - len(ban_text))
    service_profile_text = _truncate(service_profile_text, min(2500, remain // 3))
    remain2 = max(800, remain - len(service_profile_text))
    catalog = _truncate(catalog, remain2 // 3)
    existing_text = _truncate(existing_text, remain2 - len(catalog))

    pack: dict[str, Any] = {
        "system": bundle.system,
        "bundle": bundle,
        "ban_patterns": patterns,
        "api_surface_lines": surface_lines,
        "api_surface_text": surface_text,
        "catalog_text": catalog or "(none)",
        "existing_text": existing_text or "(none)",
        "bans_text": ban_text or "(none)",
        "service_profile_data": profile,
        "service_profile_text": service_profile_text,
        "schema_version": bundle.schema_version,
        "scenarios_per_skill": scenarios_per_skill,
    }
    pack["user"] = render_chunk_user(
        pack,
        service_key=service_key,
        env=env_n,
        chunk_skills=skill_ids,
        scenarios_per_skill=scenarios_per_skill,
    )
    return pack
