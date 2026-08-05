"""Stability / performance score for post-deploy soak (tech 40 + alerts 30 + business 30)."""
from __future__ import annotations

from typing import Any


def band_for_score(score: float) -> str:
    if score >= 90:
        return "STABLE"
    if score >= 75:
        return "ACCEPTABLE"
    if score >= 50:
        return "AT_RISK"
    return "UNSTABLE"


def score_technical(stats: dict[str, Any] | None, *, unavailable: bool = False) -> dict[str, Any]:
    """stats keys: p95_ok, cpu_ok, mem_ok, restart_ok, error_ok (bools). Weight 40."""
    weight = 40.0
    if unavailable:
        return {"score": 0.0, "weight": weight, "mode": "unavailable", "stats": stats or {}}
    flags = stats or {}
    checks = ["p95_ok", "cpu_ok", "mem_ok", "restart_ok", "error_ok"]
    present = [c for c in checks if c in flags]
    if not present:
        return {"score": 0.0, "weight": weight, "mode": "unavailable", "stats": flags}
    passed = sum(1 for c in present if flags.get(c))
    score = weight * (passed / len(present))
    return {"score": round(score, 2), "weight": weight, "mode": "live", "stats": flags}


def score_alerts(firing: list[dict[str, Any]] | None, *, unavailable: bool = False) -> dict[str, Any]:
    """Full 30 if none; each critical -15, each high -5; floor 0."""
    weight = 30.0
    if unavailable:
        return {"score": 0.0, "weight": weight, "mode": "unavailable", "firing": []}
    items = list(firing or [])
    score = weight
    for a in items:
        sev = str(a.get("severity") or a.get("level") or "").lower()
        if sev in {"critical", "crit"}:
            score -= 15
        elif sev in {"high", "warning", "warn"}:
            score -= 5
    score = max(0.0, score)
    return {"score": round(score, 2), "weight": weight, "mode": "live", "firing": items}


def score_business(slis: list[dict[str, Any]] | None, *, unavailable: bool = False) -> dict[str, Any]:
    """Each SLI contributes weight share of 30 if ok=True."""
    weight = 30.0
    if unavailable:
        return {"score": 0.0, "weight": weight, "mode": "unavailable", "slis": []}
    rows = list(slis or [])
    if not rows:
        return {"score": 0.0, "weight": weight, "mode": "unavailable", "slis": []}
    total_w = sum(float(s.get("weight") or 1.0) for s in rows) or 1.0
    earned = 0.0
    for s in rows:
        w = float(s.get("weight") or 1.0)
        if s.get("ok"):
            earned += weight * (w / total_w)
    return {"score": round(earned, 2), "weight": weight, "mode": "live", "slis": rows}


def compute_stability(
    *,
    technical: dict[str, Any],
    alerts: dict[str, Any],
    business: dict[str, Any],
    soak_minutes: int = 30,
    release_id: str = "",
    window: dict[str, str] | None = None,
    allow_unavailable_stable: bool = False,
) -> dict[str, Any]:
    total = float(technical.get("score") or 0) + float(alerts.get("score") or 0) + float(
        business.get("score") or 0
    )
    total = round(total, 2)
    modes = {technical.get("mode"), alerts.get("mode"), business.get("mode")}
    any_unavailable = "unavailable" in modes
    band = band_for_score(total)
    if any_unavailable and not allow_unavailable_stable and band == "STABLE":
        band = "AT_RISK"
        total = min(total, 74.99)
    system_stable = band in {"STABLE", "ACCEPTABLE"} and not (
        any_unavailable and not allow_unavailable_stable and band == "AT_RISK" and total < 75
    )
    if band in {"AT_RISK", "UNSTABLE"}:
        system_stable = False
    if band == "ACCEPTABLE":
        system_stable = True
    if band == "STABLE":
        system_stable = True

    return {
        "release_id": release_id,
        "soak_minutes": soak_minutes,
        "window": window or {},
        "pillars": {
            "technical": technical,
            "alerts": alerts,
            "business": business,
        },
        "stability_score": total,
        "band": band,
        "system_stable": system_stable,
        "any_unavailable": any_unavailable,
    }
