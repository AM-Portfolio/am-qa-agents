"""Aggregate service overview for the QA portal Services page."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from specs.catalog.catalog_loader import (
    load_openapi_document,
    load_registration,
    load_service_apis,
    reachable_target_for_service,
)
from specs.config import settings
from specs.payloads.payload_store import get_payload_set, list_payload_sets
from specs.persistence.run_store import list_runs, slim_run_for_list


def _skills_yaml_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "ui_evidence"
        / "scenario_bank"
        / "skills.yaml"
    )


def _skill_playbook_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts" / "invent" / "skills"


def _skill_summary(skill_id: str) -> str:
    """First Intent line from invent skill playbook, if present."""
    path = _skill_playbook_dir() / f"{skill_id}.md"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    in_intent = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower() == "## intent":
            in_intent = True
            continue
        if in_intent:
            if stripped.startswith("#"):
                break
            if stripped:
                return stripped[:220]
    return ""


def load_platform_skills() -> list[dict[str, Any]]:
    path = _skills_yaml_path()
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[dict[str, Any]] = []
    for row in data.get("skills") or []:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue
        env = row.get("env") if isinstance(row.get("env"), dict) else {}
        out.append(
            {
                "id": sid,
                "level": row.get("level"),
                "env_policy": env,
                "summary": _skill_summary(sid),
            }
        )
    return out


# Industry-facing labels for invent skill ids (portal coverage view).
SKILL_DISPLAY: dict[str, dict[str, str]] = {
    "data_generator": {
        "level": "Level 0",
        "name": "Data preparation",
        "category": "Setup",
        "plain": "Create or seed the data this service needs before other tests run.",
    },
    "happy_flow": {
        "level": "Level 1",
        "name": "Happy path validation",
        "category": "Functional",
        "plain": "Confirm the main success journey works end-to-end for a normal user.",
    },
    "level2_alt_path": {
        "level": "Level 2",
        "name": "Alternate path validation",
        "category": "Functional",
        "plain": "Confirm a different valid order of calls still reaches a good outcome.",
    },
    "validation": {
        "level": "Level 2",
        "name": "Input validation",
        "category": "Negative",
        "plain": "Confirm bad or incomplete input is rejected with a clear client error.",
    },
    "level3_edge": {
        "level": "Level 3",
        "name": "Edge case validation",
        "category": "Boundary",
        "plain": "Confirm awkward but legal values and boundary conditions behave safely.",
    },
    "null_point": {
        "level": "Level 3",
        "name": "Missing resource validation",
        "category": "Negative",
        "plain": "Confirm unknown or missing resources return not-found or empty results.",
    },
    "tweak_data": {
        "level": "Level 3",
        "name": "State change validation",
        "category": "Functional",
        "plain": "Confirm a small legitimate update changes what the service returns later.",
    },
    "level4_state": {
        "level": "Level 4",
        "name": "Lifecycle validation",
        "category": "Integration",
        "plain": "Confirm multi-step lifecycle transitions (pause, resume, cancel, upgrade).",
    },
    "level5_abuse": {
        "level": "Level 5",
        "name": "Abuse & illegal transition",
        "category": "Security",
        "plain": "Confirm illegal or abusive state toggles are blocked without breaking the service.",
    },
    "security": {
        "level": "Level 5",
        "name": "Auth & access control",
        "category": "Security",
        "plain": "Confirm protected APIs reject missing or wrong credentials.",
    },
}


def skill_display(skill_id: str) -> dict[str, str]:
    meta = SKILL_DISPLAY.get(skill_id) or {}
    level = meta.get("level") or "?"
    name = meta.get("name") or skill_id.replace("_", " ").title()
    plain = meta.get("plain") or ""
    return {
        "id": skill_id,
        "level": level,
        "name": name,
        "category": meta.get("category") or "Other",
        "plain": plain,
        "label": f"{level} · {name}",
    }


def _overlay_text(overlay: Any) -> str:
    if overlay is None:
        return ""
    if isinstance(overlay, str):
        return overlay.strip()[:240]
    if isinstance(overlay, dict):
        for key in ("summary", "hint", "notes", "focus", "title"):
            if overlay.get(key):
                return str(overlay[key]).strip()[:240]
        return ", ".join(f"{k}={v}" for k, v in list(overlay.items())[:4])[:240]
    if isinstance(overlay, list):
        return "; ".join(str(x) for x in overlay[:4])[:240]
    return str(overlay)[:240]


def _plugin_use_cases(service_key: str) -> list[dict[str, Any]]:
    """Catalog flows from plugin apis.yaml as visible use-cases."""
    try:
        from ui_evidence.plugins.loader import catalog_bundle, get_plugin
    except Exception:  # noqa: BLE001
        return []
    p = get_plugin(plugin_id=service_key, include_disabled=True)
    if p is None:
        return []
    try:
        bundle = catalog_bundle(p)
    except Exception:  # noqa: BLE001
        return []
    apis = bundle.get("apis") if isinstance(bundle.get("apis"), dict) else {}
    flows = apis.get("flows") if isinstance(apis, dict) else []
    out: list[dict[str, Any]] = []
    for flow in flows or []:
        if not isinstance(flow, dict):
            continue
        steps = flow.get("steps") if isinstance(flow.get("steps"), list) else []
        step_bits = []
        for st in steps[:6]:
            if not isinstance(st, dict):
                continue
            bit = st.get("path_contains") or st.get("tool_match") or st.get("id") or ""
            if isinstance(bit, list):
                bit = ",".join(str(x) for x in bit)
            method = str(st.get("method") or "").upper()
            step_bits.append(f"{method} {bit}".strip())
        out.append(
            {
                "id": flow.get("id"),
                "title": flow.get("title") or flow.get("id"),
                "source": "plugin_catalog",
                "skill": None,
                "gate": flow.get("gate"),
                "steps_count": len(steps),
                "steps_preview": step_bits,
                "scenarios_count": 0,
            }
        )
    # Hand .feature files still in plugin features/ dir
    for name in bundle.get("features") or []:
        out.append(
            {
                "id": name,
                "title": str(name).replace(".feature", "").replace("_", " "),
                "source": "plugin_feature_file",
                "skill": None,
                "gate": None,
                "steps_count": 0,
                "steps_preview": [],
                "scenarios_count": 0,
            }
        )
    return out


def _build_use_cases(
    *,
    features: list[dict[str, Any]],
    invent_profile: dict[str, Any] | None,
    scenarios_detail: list[dict[str, Any]],
    plugin_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prefer invent scenarios (with steps) for portal; features are title fallbacks only."""
    out: list[dict[str, Any]] = []

    def _annotate(case: dict[str, Any]) -> dict[str, Any]:
        sk = str(case.get("skill") or "")
        disp = skill_display(sk) if sk else {
            "label": "Catalog · Flows",
            "name": "Catalog flows",
            "level": "—",
            "category": "Catalog",
        }
        return {
            **case,
            "display_label": disp.get("label"),
            "display_name": disp.get("name"),
            "display_level": disp.get("level"),
            "category": disp.get("category"),
        }

    # Scenarios first — rich steps for modern coverage UI
    if scenarios_detail:
        for row in scenarios_detail:
            steps = [
                f"{(st.get('method') or '').upper()} {st.get('path') or st.get('path_contains') or ''}".strip()
                for st in (row.get("steps") or [])[:6]
                if isinstance(st, dict)
            ]
            out.append(
                _annotate(
                    {
                        "id": row.get("dedupe_key") or row.get("id"),
                        "title": row.get("title")
                        or row.get("dedupe_key")
                        or "scenario",
                        "source": "bank_scenario",
                        "skill": row.get("skill"),
                        "gate": None,
                        "steps_count": len(row.get("steps") or []),
                        "steps_preview": steps,
                        "scenarios_count": 1,
                        "tags": [],
                        "status": row.get("status"),
                    }
                )
            )
    else:
        for f in features:
            out.append(
                _annotate(
                    {
                        "id": f.get("feature_id"),
                        "title": f.get("title") or f.get("feature_id"),
                        "source": "bank_feature",
                        "skill": f.get("skill"),
                        "gate": None,
                        "steps_count": int(f.get("scenarios_count") or 0),
                        "steps_preview": [],
                        "scenarios_count": int(f.get("scenarios_count") or 0),
                        "tags": f.get("tags") or [],
                    }
                )
            )

    seen_titles = {str(x.get("title") or "").lower() for x in out}
    for case in plugin_cases:
        title = str(case.get("title") or "").lower()
        if title and title in seen_titles:
            continue
        out.append(_annotate(case))

    if invent_profile and not out:
        domain = str(invent_profile.get("domain") or "").strip()
        surface = invent_profile.get("api_surface") or invent_profile.get("tools") or []
        preview = []
        if isinstance(surface, list):
            for item in surface[:8]:
                if isinstance(item, dict):
                    preview.append(
                        f"{item.get('method') or ''} {item.get('path') or item.get('path_contains') or ''}".strip()
                    )
                else:
                    preview.append(str(item))
        out.append(
            _annotate(
                {
                    "id": "invent_profile",
                    "title": domain
                    or "Invent profile surface (bank empty — run invent)",
                    "source": "invent_profile",
                    "skill": None,
                    "gate": None,
                    "steps_count": len(preview),
                    "steps_preview": preview,
                    "scenarios_count": 0,
                    "tags": ["needs_invent"],
                }
            )
        )
    return out


def _plugin_summary(service_key: str) -> dict[str, Any] | None:
    try:
        from ui_evidence.plugins.loader import get_plugin, list_plugins
    except Exception:  # noqa: BLE001
        return None
    p = get_plugin(plugin_id=service_key, include_disabled=True)
    if p is None:
        for row in list_plugins(include_disabled=True):
            if str(row.get("spt_service_id") or "") == service_key:
                return row
        return None
    return p.summary()


def _bank_sections(
    service_key: str, env: str
) -> tuple[
    dict[str, Any] | None,
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    str | None,
]:
    """invent_profile, features, scenarios summary, coverage, scenario samples, bank_error."""
    empty_scenarios = {
        "count": 0,
        "invent_complete": False,
        "needs_reinvent": False,
        "by_skill": {},
    }
    try:
        from ui_evidence.scenario_bank.bank_store import load_bank
        from ui_evidence.scenario_bank.repo import get_repo
    except Exception as exc:  # noqa: BLE001
        return None, [], empty_scenarios, {}, [], str(exc)

    bank_error: str | None = None
    invent_profile: dict[str, Any] | None = None
    features: list[dict[str, Any]] = []
    coverage: dict[str, Any] = {}
    scenarios: dict[str, Any] = dict(empty_scenarios)
    samples: list[dict[str, Any]] = []
    try:
        repo = get_repo()
        invent_profile = repo.get_profile(service_key, env) or None
        if invent_profile == {}:
            invent_profile = None
        features = [
            {
                "feature_id": f.get("feature_id"),
                "title": f.get("title") or f.get("name") or f.get("feature_id"),
                "scenarios_count": f.get("scenarios_count")
                or len(f.get("scenarios") or f.get("scenario_ids") or []),
                "skill": f.get("skill"),
                "tags": f.get("tags") or [],
            }
            for f in (repo.list_features(service_key, env) or [])
        ]
        kn = repo.get_knowledge(service_key, env) or {}
        coverage = {
            "quality_score": kn.get("quality_score") or kn.get("score"),
            "skill_coverage": kn.get("skill_coverage"),
            "surface_coverage": kn.get("surface_coverage"),
            "reasons": kn.get("reasons") or kn.get("quality_reasons") or [],
            "updated_at": kn.get("updated_at"),
        }
        data = load_bank(service_key, env)
        rows = list(data.get("scenarios") or [])
        by_skill = Counter(str(r.get("skill") or "unknown") for r in rows)
        scenarios = {
            "count": len(rows),
            "invent_complete": bool(data.get("invent_complete")),
            "needs_reinvent": bool(data.get("needs_reinvent")),
            "by_skill": dict(sorted(by_skill.items())),
        }
        for r in rows[:40]:
            if not isinstance(r, dict):
                continue
            samples.append(
                {
                    "id": r.get("id") or r.get("dedupe_key"),
                    "dedupe_key": r.get("dedupe_key"),
                    "title": r.get("title") or r.get("dedupe_key"),
                    "skill": r.get("skill"),
                    "steps": r.get("steps") or [],
                }
            )
    except Exception as exc:  # noqa: BLE001
        bank_error = str(exc)
    return invent_profile, features, scenarios, coverage, samples, bank_error


def _skills_with_counts(
    platform: list[dict[str, Any]],
    invent_profile: dict[str, Any] | None,
    by_skill: dict[str, int],
    *,
    environment: str,
) -> list[dict[str, Any]]:
    overlays = {}
    if invent_profile and isinstance(invent_profile.get("skill_overlays"), dict):
        overlays = invent_profile["skill_overlays"]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in platform:
        sid = row["id"]
        seen.add(sid)
        policy = row.get("env_policy") if isinstance(row.get("env_policy"), dict) else {}
        disp = skill_display(sid)
        out.append(
            {
                **row,
                "level": disp["level"],
                "display_name": disp["name"],
                "display_label": disp["label"],
                "category": disp["category"],
                "plain_english": disp.get("plain") or row.get("summary") or "",
                "bank_count": int(by_skill.get(sid) or 0),
                "overlay": overlays.get(sid),
                "overlay_text": _overlay_text(overlays.get(sid)),
                "env_action": policy.get(environment) or policy.get("dev") or "—",
            }
        )
    for sid, count in by_skill.items():
        if sid in seen:
            continue
        disp = skill_display(sid)
        out.append(
            {
                "id": sid,
                "level": disp["level"],
                "display_name": disp["name"],
                "display_label": disp["label"],
                "category": disp["category"],
                "plain_english": disp.get("plain") or _skill_summary(sid),
                "env_policy": {},
                "summary": _skill_summary(sid),
                "bank_count": int(count),
                "overlay": overlays.get(sid),
                "overlay_text": _overlay_text(overlays.get(sid)),
                "env_action": "—",
            }
        )
    # Stable industry order L0 → L5
    order = {k: i for i, k in enumerate(SKILL_DISPLAY.keys())}
    out.sort(key=lambda r: (order.get(str(r.get("id") or ""), 99), str(r.get("id"))))
    return out


def _payload_summary(service_key: str) -> dict[str, Any]:
    try:
        sets = list_payload_sets(service_key)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "active_version": None, "api_count": 0, "count": 0}
    active_ver = sets.get("active_version")
    api_count = 0
    label = None
    if active_ver is not None:
        full = get_payload_set(service_key, int(active_ver))
        if full:
            apis = full.get("apis") or full.get("payloads") or {}
            if isinstance(apis, dict):
                api_count = len(apis)
            elif isinstance(apis, list):
                api_count = len(apis)
            label = full.get("label")
    return {
        "ok": True,
        "active_version": active_ver,
        "active_label": label,
        "api_count": api_count,
        "count": sets.get("count") or 0,
        "sets": sets.get("sets") or [],
    }


def _metrics_from_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {
            "run_count": 0,
            "by_status": {},
            "recent_pass_rate": None,
            "last_p90_ms": None,
            "last_fail_pct": None,
            "last_rps": None,
        }
    by_status = Counter(str(r.get("status") or "unknown") for r in runs)
    finished = [r for r in runs if r.get("status") not in ("running", "queued", None)]
    sample = finished[:25] if finished else runs[:25]
    passed_n = sum(1 for r in sample if r.get("passed") is True or r.get("status") == "passed")
    rate = round(100.0 * passed_n / len(sample), 1) if sample else None
    latest = runs[0]
    return {
        "run_count": len(runs),
        "by_status": dict(sorted(by_status.items())),
        "recent_pass_rate": rate,
        "last_p90_ms": latest.get("p90_ms"),
        "last_fail_pct": latest.get("fail_pct"),
        "last_rps": latest.get("rps"),
    }


def _openapi_stub_from_registration(
    service_key: str,
    reg: dict[str, Any] | None,
    *,
    target: str | None,
    env: str,
) -> dict[str, Any]:
    """Fast OpenAPI summary without live multi-URL fanout (avoids 10–30s portal timeouts)."""
    oas = (reg or {}).get("openapi") if isinstance((reg or {}).get("openapi"), dict) else {}
    path = str(oas.get("path") or "/openapi.json")
    url = f"{(target or '').rstrip('/')}{path}" if target else None
    return {
        "ok": False,
        "url": url,
        "path_count": None,
        "operation_count": None,
        "version": None,
        "title": (reg or {}).get("label") or service_key,
        "error": None,
        "document_available": False,
        "live_skipped": True,
        "registered_path": path,
        "environment": env,
    }


def build_service_overview(
    service_key: str,
    *,
    environment: str | None = None,
    runs_limit: int = 25,
    live_openapi: bool = False,
) -> dict[str, Any]:
    env = environment or settings.default_environment
    limit = max(1, min(int(runs_limit or 25), 100))
    reg = load_registration(service_key)
    service_row = {
        "id": service_key,
        "label": (reg or {}).get("label") or service_key,
        "runtime": (reg or {}).get("runtime"),
        "registered": reg is not None,
    }

    apis_data: dict[str, Any] = {}
    catalog_error: str | None = None
    target = reachable_target_for_service(service_key, env)
    if live_openapi:
        try:
            apis_data = load_service_apis(service_key, env) or {}
        except Exception as exc:  # noqa: BLE001
            catalog_error = str(exc)
    else:
        # Avoid live OpenAPI fanout inside load_service_apis (same multi-URL cost).
        try:
            from specs.catalog.catalog_loader import _load_baked_apis

            apis_data = _load_baked_apis(service_key) or {}
        except Exception as exc:  # noqa: BLE001
            catalog_error = str(exc)
            apis_data = {"apis": [], "runtime": (reg or {}).get("runtime")}
    apis = apis_data.get("apis") or []

    openapi_meta: dict[str, Any]
    if live_openapi:
        try:
            raw = load_openapi_document(service_key, env)
            openapi_meta = {
                "ok": bool(raw.get("ok")),
                "url": raw.get("openapi_url"),
                "path_count": raw.get("path_count"),
                "operation_count": raw.get("operation_count"),
                "version": raw.get("version"),
                "title": raw.get("title"),
                "error": raw.get("error"),
                "document_available": bool(
                    raw.get("ok") and isinstance(raw.get("document"), dict)
                ),
                "live_skipped": False,
            }
        except Exception as exc:  # noqa: BLE001
            openapi_meta = {
                "ok": False,
                "url": None,
                "path_count": None,
                "operation_count": None,
                "version": None,
                "title": None,
                "error": str(exc),
                "document_available": False,
                "live_skipped": False,
            }
    else:
        openapi_meta = _openapi_stub_from_registration(
            service_key, reg, target=target, env=env
        )

    invent_profile, features, scenarios, coverage, scenario_samples, bank_error = (
        _bank_sections(service_key, env)
    )
    if not apis and invent_profile:
        surface = invent_profile.get("api_surface") or invent_profile.get("tools") or []
        if isinstance(surface, list) and surface:
            apis = surface
            apis_data = {
                **apis_data,
                "apis": surface,
                "source": "invent_profile",
                "runtime": apis_data.get("runtime") or (reg or {}).get("runtime"),
            }
    platform_skills = load_platform_skills()
    skills = _skills_with_counts(
        platform_skills,
        invent_profile,
        scenarios.get("by_skill") or {},
        environment=env,
    )
    plugin_cases = _plugin_use_cases(service_key)
    use_cases = _build_use_cases(
        features=features,
        invent_profile=invent_profile,
        scenarios_detail=scenario_samples,
        plugin_cases=plugin_cases,
    )

    runs_rows: list[dict[str, Any]] = []
    runs_total = 0
    runs_error: str | None = None
    try:
        rows, runs_total = list_runs(limit=limit, offset=0, service=service_key)
        # Prefer same-env runs first while keeping total from full service filter
        env_rows = [r for r in rows if str(r.get("environment") or "") == env]
        use = env_rows if env_rows else rows
        runs_rows = [slim_run_for_list(r) for r in use[:limit]]
    except Exception as exc:  # noqa: BLE001
        runs_error = str(exc)

    warnings: list[str] = []
    if catalog_error:
        warnings.append(f"catalog: {catalog_error}")
    if bank_error:
        warnings.append(f"bank: {bank_error}")
    if runs_error:
        warnings.append(f"runs: {runs_error}")
    if live_openapi and not openapi_meta.get("ok"):
        warnings.append(f"openapi: {openapi_meta.get('error') or 'unavailable'}")
    elif openapi_meta.get("live_skipped"):
        # Not a failure — OpenAPI page does the live fetch; keep overview snappy.
        pass
    if scenarios.get("count", 0) == 0 and not features:
        warnings.append(
            "bank: no invented scenarios/features yet — showing plugin catalog flows"
        )

    return {
        "ok": True,
        "service": service_row,
        "environment": env,
        "plugin": _plugin_summary(service_key),
        "catalog": {
            "apis_count": len(apis),
            "target_url": target,
            "runtime": service_row.get("runtime") or apis_data.get("runtime"),
            "openapi_version": apis_data.get("openapi_version"),
        },
        "openapi": openapi_meta,
        "payloads": _payload_summary(service_key),
        "skills": skills,
        "invent_profile": invent_profile,
        "features": features,
        "use_cases": use_cases,
        "scenarios": scenarios,
        "coverage": coverage,
        "runs": runs_rows,
        "runs_total": runs_total,
        "metrics": _metrics_from_runs(runs_rows),
        "warnings": warnings,
        "partial": bool(warnings),
    }
