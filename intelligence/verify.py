"""Post-test verification gate — Phase 2 (§14.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _policy() -> dict[str, Any]:
    cfg = Path(__file__).resolve().parents[1] / "config" / "release-policy.yaml"
    if cfg.is_file():
        with open(cfg, encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("policy") or {}
    return {}


def post_test_verify(
    *,
    smoke: dict[str, Any],
    comparisons: dict[str, Any],
    gnx_mode: str | None = None,
    fin_prep: dict[str, Any] | None = None,
    matrix_results: dict[str, Any] | None = None,
    open_work_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pol = _policy()
    warnings: list[str] = []
    blockers: list[str] = []
    clean_pol = pol.get("clean_feature") or {}

    # UI / smoke (also used as matrix UI layer status)
    st = str(smoke.get("status") or "").lower()
    skipped = bool(smoke.get("skipped"))
    if not skipped and st not in {"completed", "done", "succeeded", "success", "passed", ""}:
        if pol.get("block_on_p0_fail", True):
            blockers.append(f"smoke_status:{st or 'missing'}")
        else:
            warnings.append(f"smoke_status:{st or 'missing'}")

    # SAST findings (Phase 4)
    for b in (matrix_results or {}).get("sast_blockers") or []:
        blockers.append(str(b) if str(b).startswith("sast:") else f"sast:{b}")
    security = (matrix_results or {}).get("security") or {}
    for b in security.get("blockers") or []:
        if b not in blockers:
            blockers.append(b)

    # Matrix P0 failures (Phase 3)
    for failed_id in (matrix_results or {}).get("p0_failed") or []:
        if clean_pol.get("require_p0_pass", True) or pol.get("block_on_p0_fail", True):
            blockers.append(f"matrix_p0_fail:{failed_id}")
        else:
            warnings.append(f"matrix_p0_fail:{failed_id}")

    # Open work items (clean-feature policy)
    for wi in open_work_items or []:
        sev = str(wi.get("severity") or wi.get("priority") or "").upper()
        wid = wi.get("id") or wi.get("work_item_id") or "unknown"
        if sev in {"P0", "CRITICAL"} and clean_pol.get("block_on_open_p0_work_item", True):
            blockers.append(f"open_work_item_p0:{wid}")
        elif sev in {"P1", "HIGH"} and clean_pol.get("warn_on_open_p1_work_item", True):
            warnings.append(f"open_work_item_p1:{wid}")

    # Latency flags
    for ep in comparisons.get("endpoints") or []:
        flags = ep.get("delta_flags") or []
        label = f"{ep.get('service')}:{ep.get('route')}"
        if "p95_block" in flags:
            blockers.append(f"latency_p95_block:{label}")
        elif "p95_warn" in flags:
            warnings.append(f"latency_p95_warn:{label}")

    # Resources
    res_pol = pol.get("resources") or {}
    cpu_ceil = float(res_pol.get("cpu_max_pct_limit") or 90)
    mem_ceil = float(res_pol.get("memory_max_pct_limit") or 90)
    max_restart = int(res_pol.get("max_restart_delta") or 2)
    for res in comparisons.get("resources") or []:
        dep = res.get("deployment")
        cpu_max = float(((res.get("cpu") or {}).get("max_pct_limit") or {}).get("r") or 0)
        mem_max = float(((res.get("memory") or {}).get("max_pct_limit") or {}).get("r") or 0)
        oom = int(res.get("oom_killed") or 0)
        rb = int(((res.get("restarts") or {}).get("b") or 0))
        rr = int(((res.get("restarts") or {}).get("r") or 0))
        if oom > 0 and pol.get("block_on_oom", True):
            blockers.append(f"oom:{dep}")
        if cpu_max > cpu_ceil:
            warnings.append(f"cpu_high:{dep}:{cpu_max}")
        if mem_max > mem_ceil:
            warnings.append(f"memory_high:{dep}:{mem_max}")
        if (rr - rb) > max_restart and pol.get("block_on_crashloop", True):
            blockers.append(f"restarts:{dep}:{rr - rb}")

    # Users / 5xx
    users = comparisons.get("users") or {}
    err_pol = pol.get("errors") or {}
    five_b = int((users.get("user_facing_5xx") or {}).get("b") or 0)
    five_r = int((users.get("user_facing_5xx") or {}).get("r") or 0)
    if (five_r - five_b) > int(err_pol.get("max_5xx_delta") or 5):
        warnings.append(f"user_5xx_delta:{five_r - five_b}")

    if gnx_mode == "degraded" and pol.get("warn_on_gnx_degraded", True):
        warnings.append("gnx_mode:degraded")

    fin_st = str((fin_prep or {}).get("status") or "")
    if fin_st in {"FAILED"}:
        warnings.append(f"fin_prep:{fin_st}")

    feature_blockers = [
        b
        for b in blockers
        if b.startswith("smoke_")
        or b.startswith("latency_")
        or b.startswith("matrix_p0_")
        or b.startswith("open_work_item_p0")
        or b.startswith("sast:")
    ]
    feature_clean = len(feature_blockers) == 0
    infra_clean = not any(b.startswith("oom:") or b.startswith("restarts:") for b in blockers)
    verified = len(blockers) == 0

    summary_parts = []
    if verified:
        summary_parts.append("gates_passed")
    else:
        summary_parts.append(f"blockers={len(blockers)}")
    if warnings:
        summary_parts.append(f"warnings={len(warnings)}")

    return {
        "verified": verified,
        "warnings": warnings,
        "blockers": blockers,
        "feature_clean": feature_clean and verified,
        "infra_clean": infra_clean,
        "comparison_summary": ";".join(summary_parts),
        "releasable": verified,
    }
