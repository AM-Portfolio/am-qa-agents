"""Deterministic test matrix ranker — Phase 3 (§23.3)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _policy() -> dict[str, Any]:
    cfg = Path(__file__).resolve().parents[1] / "config" / "release-policy.yaml"
    if cfg.is_file():
        with open(cfg, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_smoke_defaults() -> dict[str, Any]:
    cfg = Path(__file__).resolve().parents[1] / "config" / "smoke-defaults.yaml"
    if not cfg.is_file():
        return {}
    with open(cfg, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("smoke_defaults") or {}


def _tier_for_score(score: float, thresholds: dict[str, float]) -> str:
    if score >= float(thresholds.get("p0") or 80):
        return "P0"
    if score >= float(thresholds.get("p1") or 40):
        return "P1"
    return "P2"


def _intent_aligns(candidate: dict[str, Any], change_intent: dict[str, Any] | None) -> bool:
    if not change_intent:
        return False
    focus = change_intent.get("suggested_test_focus") or []
    if not isinstance(focus, list):
        return False
    svc = str(candidate.get("service") or "").lower()
    profile = str(candidate.get("ui_profile") or "").lower()
    repo = str(candidate.get("repo") or "").lower()
    for item in focus:
        if not isinstance(item, dict):
            continue
        if profile and str(item.get("ui_profile") or "").lower() == profile:
            return True
        for sc in item.get("fin_scenarios") or []:
            if str(sc).lower() in str(candidate.get("id") or "").lower():
                return True
        if svc and svc in str(item).lower():
            return True
        if repo and repo in str(item.get("repo") or "").lower():
            return True
    flows = [str(f).lower() for f in (change_intent.get("affected_user_flows") or [])]
    if candidate.get("layer") == "flow" and any(f in str(candidate.get("id") or "").lower() for f in flows):
        return True
    return False


def _candidate(
    *,
    cid: str,
    layer: str,
    score: float,
    service: str | None = None,
    ui_profile: str | None = None,
    repo: str | None = None,
    source: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": cid,
        "layer": layer,  # api | ui | flow
        "score": score,
        "service": service,
        "ui_profile": ui_profile,
        "repo": repo,
        "source": source,
        "meta": meta or {},
    }


def collect_candidates(
    *,
    load_context: dict[str, Any],
    index: dict[str, Any] | None = None,
    change_intent: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build unordered candidate pool from impact ∪ load-rules ∪ smoke ∪ SPT stubs."""
    index = index or {}
    lc = load_context or {}
    fin = lc.get("fin") or {}
    ui = lc.get("ui") or {}
    webhook = lc.get("webhook") or {}
    repo = str(webhook.get("repo") or "")
    short = repo.split("/")[-1] if repo else ""
    gnx_mode = str(index.get("gnx_mode") or "full")
    docs_only = bool(lc.get("docs_only"))

    cands: list[dict[str, Any]] = []
    impact_tier = 30.0 if gnx_mode == "full" else 10.0

    # API layer from load-rules / fin services
    for svc in fin.get("services") or []:
        name = svc.get("name") if isinstance(svc, dict) else str(svc)
        if not name:
            continue
        cands.append(
            _candidate(
                cid=f"api:{name}",
                layer="api",
                score=50 + impact_tier,
                service=name,
                repo=short,
                source="load_rules",
            )
        )
    for sc in fin.get("scenarios") or []:
        cands.append(
            _candidate(
                cid=f"api-scenario:{sc}",
                layer="api",
                score=55 + impact_tier,
                service=None,
                repo=short,
                source="load_rules",
                meta={"scenario": sc},
            )
        )

    # UI layer
    profile = ui.get("profile") or "SMOKE"
    cands.append(
        _candidate(
            cid=f"ui:{profile}",
            layer="ui",
            score=60 + impact_tier,
            ui_profile=str(profile),
            repo=short,
            source="load_rules",
            meta={"target_url": ui.get("target_url"), "ui_mode": ui.get("ui_mode")},
        )
    )

    # Flow layer (SPT stub from env capabilities / scenarios)
    for flow in (change_intent or {}).get("affected_user_flows") or []:
        cands.append(
            _candidate(
                cid=f"flow:{flow}",
                layer="flow",
                score=45 + impact_tier,
                repo=short,
                source="change_intent_flow",
                meta={"flow": flow},
            )
        )
    if not docs_only and fin.get("scenarios"):
        for sc in fin["scenarios"]:
            cands.append(
                _candidate(
                    cid=f"flow:{sc}",
                    layer="flow",
                    score=40 + impact_tier,
                    repo=short,
                    source="scenario_flow",
                    meta={"flow": sc},
                )
            )

    # Impact symbols (if index returned any)
    for sym in (index.get("impact_symbols") or [])[:20]:
        name = sym if isinstance(sym, str) else str(sym.get("name") or sym.get("symbol") or "")
        if not name:
            continue
        cands.append(
            _candidate(
                cid=f"impact:{name}",
                layer="api",
                score=70 + impact_tier,
                repo=short,
                source="gitnexus_impact",
                meta={"symbol": name},
            )
        )

    # SPT catalog playbooks
    try:
        from intelligence.catalog import playbook_candidates_for_repo, spt_priority

        for pb in playbook_candidates_for_repo(repo):
            pri = spt_priority(pb)
            tiers = pb.get("tiers") or {}
            ui_t = tiers.get("ui") or {}
            if ui_t.get("profile"):
                cands.append(
                    _candidate(
                        cid=f"spt-ui:{pb.get('id')}:{ui_t['profile']}",
                        layer="ui",
                        score=pri + impact_tier,
                        ui_profile=str(ui_t["profile"]),
                        repo=short,
                        source="spt_catalog",
                    )
                )
            for sc in (tiers.get("api") or {}).get("scenarios") or []:
                cands.append(
                    _candidate(
                        cid=f"spt-api:{pb.get('id')}:{sc}",
                        layer="api",
                        score=pri + impact_tier,
                        repo=short,
                        source="spt_catalog",
                        meta={"scenario": sc},
                    )
                )
            for flow in tiers.get("flow") or []:
                cands.append(
                    _candidate(
                        cid=f"spt-flow:{pb.get('id')}:{flow}",
                        layer="flow",
                        score=pri + impact_tier - 5,
                        repo=short,
                        source="spt_catalog",
                        meta={"flow": flow},
                    )
                )
    except Exception:  # noqa: BLE001 — catalog optional
        pass

    # L3 smoke floor
    smoke = _load_smoke_defaults()
    if gnx_mode == "degraded" or docs_only:
        cands.append(
            _candidate(
                cid=f"ui:{smoke.get('profile') or 'SMOKE'}",
                layer="ui",
                score=float(smoke.get("smoke_floor") or 35),
                ui_profile=str(smoke.get("profile") or "SMOKE"),
                repo=short,
                source="smoke_defaults",
            )
        )
        for name in smoke.get("fin_services") or []:
            cands.append(
                _candidate(
                    cid=f"api:{name}",
                    layer="api",
                    score=float(smoke.get("smoke_floor") or 35),
                    service=name,
                    repo=short,
                    source="smoke_defaults",
                )
            )

    # Deduplicate by id, keep highest score
    by_id: dict[str, dict[str, Any]] = {}
    for c in cands:
        prev = by_id.get(c["id"])
        if prev is None or c["score"] > prev["score"]:
            by_id[c["id"]] = c
    return list(by_id.values())


def rank_matrix(
    *,
    load_context: dict[str, Any],
    index: dict[str, Any] | None = None,
    change_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Rank candidates and assign P0/P1/P2.

    ChangeIntent only adds advisory_boost when aligned — never alone creates P0.
    """
    pol = _policy()
    matrix_pol = pol.get("matrix") or {}
    thresholds = matrix_pol.get("tier_thresholds") or {"p0": 80, "p1": 40}
    advisory_boost = float(matrix_pol.get("advisory_boost") or 8)
    smoke_floor = float(matrix_pol.get("smoke_floor") or 35)
    gnx_mode = str((index or {}).get("gnx_mode") or "full")

    raw = collect_candidates(
        load_context=load_context, index=index, change_intent=change_intent
    )
    ranked: list[dict[str, Any]] = []
    for c in raw:
        score = float(c["score"])
        aligned = _intent_aligns(c, change_intent)
        if aligned:
            score += advisory_boost
            c["advisory_boost"] = advisory_boost
        else:
            c["advisory_boost"] = 0
        if gnx_mode == "degraded":
            score = max(score, smoke_floor)
        c["score"] = score
        # Hard rule: advisory alone cannot create P0 — require graph/load_rules source
        tier = _tier_for_score(score, thresholds)
        if tier == "P0" and c.get("source") == "change_intent_flow" and not aligned:
            tier = "P1"
        if tier == "P0" and c.get("source") == "change_intent_flow" and c.get("advisory_boost") and score - advisory_boost < float(
            thresholds.get("p0") or 80
        ):
            # Would not be P0 without advisory → demote to P1
            tier = "P1"
            c["demoted_from_p0"] = "advisory_alone"
        c["tier"] = tier
        c["release_blocker"] = tier == "P0"
        ranked.append(c)

    ranked.sort(key=lambda x: (-float(x["score"]), x["id"]))
    by_layer = {"api": [], "ui": [], "flow": []}
    for item in ranked:
        layer = item.get("layer") or "api"
        if layer in by_layer:
            by_layer[layer].append(item)

    return {
        "matrix_id": f"mx-{(load_context or {}).get('load_context_id') or 'anon'}",
        "gnx_mode": gnx_mode,
        "items": ranked,
        "by_layer": by_layer,
        "p0": [i for i in ranked if i["tier"] == "P0"],
        "p1": [i for i in ranked if i["tier"] == "P1"],
        "p2": [i for i in ranked if i["tier"] == "P2"],
        "summary": {
            "total": len(ranked),
            "p0": len([i for i in ranked if i["tier"] == "P0"]),
            "p1": len([i for i in ranked if i["tier"] == "P1"]),
            "p2": len([i for i in ranked if i["tier"] == "P2"]),
        },
    }


def matrix_execution_plan(matrix: dict[str, Any], load_context: dict[str, Any]) -> dict[str, Any]:
    """Derive what specialists should run from ranked matrix (P0+P1 by default)."""
    run_tiers = set(
        os.getenv("QA_AGENT_MATRIX_TIERS", "P0,P1").upper().split(",")
    )
    items = [i for i in (matrix.get("items") or []) if i.get("tier") in run_tiers]
    ui_profiles = []
    fin_services = []
    scenarios = []
    flows = []
    for i in items:
        if i.get("layer") == "ui" and i.get("ui_profile"):
            ui_profiles.append(i["ui_profile"])
        if i.get("layer") == "api" and i.get("service"):
            fin_services.append(i["service"])
        if i.get("layer") == "api" and (i.get("meta") or {}).get("scenario"):
            scenarios.append(i["meta"]["scenario"])
        if i.get("layer") == "flow":
            flows.append((i.get("meta") or {}).get("flow") or i.get("id"))

    ui = (load_context or {}).get("ui") or {}
    primary_ui = ui_profiles[0] if ui_profiles else ui.get("profile") or "SMOKE"
    return {
        "ui_profile": primary_ui,
        "ui_profiles": list(dict.fromkeys(ui_profiles)),
        "fin_services": list(dict.fromkeys(fin_services)),
        "scenarios": list(dict.fromkeys(scenarios)),
        "flows": list(dict.fromkeys(flows)),
        "items_scheduled": [i["id"] for i in items],
        "specification": (
            f"Phase 3 matrix: tiers={sorted(run_tiers)}; "
            f"ui={primary_ui}; services={fin_services[:5]}; flows={flows[:5]}"
        ),
    }
