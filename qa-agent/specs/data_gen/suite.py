"""Suite engine: filter payload set → selected_api_ids + expect_status for SPT."""
from __future__ import annotations

from typing import Any

from specs.data_gen.constants import (
    PAYLOAD_SET_LABEL_PREFIX,
    SUITE_CASE_KINDS,
)
from specs.data_gen.pack import disk_profile_for_suite
from specs.payloads.payload_store import get_payload_set, list_payload_sets, set_active_payload_set


def normalize_suite(suite: str | None) -> str:
    s = (suite or "default").strip().lower()
    if s in {"working", "prod"}:
        return "default"
    return s if s in SUITE_CASE_KINDS else "default"


def case_kinds_for_suite(suite: str, override: list[str] | None = None) -> frozenset[str]:
    if override:
        return frozenset(str(x).strip().lower() for x in override if str(x).strip())
    return SUITE_CASE_KINDS.get(normalize_suite(suite), SUITE_CASE_KINDS["default"])


def find_data_gen_payload_set(service: str, profile: str) -> dict[str, Any] | None:
    """Return set summary matching label data-gen-{profile} (active preferred)."""
    disk = disk_profile_for_suite(profile)
    want_labels = {
        f"{PAYLOAD_SET_LABEL_PREFIX}{disk}",
        f"{PAYLOAD_SET_LABEL_PREFIX}{profile}",
        f"{PAYLOAD_SET_LABEL_PREFIX}prod" if disk == "prod" else "",
    }
    want_labels.discard("")
    meta = list_payload_sets(service)
    sets = list(meta.get("sets") or []) if isinstance(meta, dict) else []
    active = meta.get("active_version") if isinstance(meta, dict) else None
    # Prefer active if label matches
    for row in sets:
        if int(row.get("version") or 0) == int(active or -1):
            if str(row.get("label") or "") in want_labels:
                return row
    for row in sorted(sets, key=lambda r: int(r.get("version") or 0), reverse=True):
        if str(row.get("label") or "") in want_labels:
            return row
    return None


def api_ids_for_suite(
    service: str,
    suite: str,
    *,
    version: int | None = None,
    case_kinds: list[str] | None = None,
) -> dict[str, Any]:
    """Select api_ids whose primary meta.case_kind is in suite filter.

    Technical rows without expect_status are excluded with a warning.
    """
    kinds = case_kinds_for_suite(suite, case_kinds)
    # Never include cross_flow in k6 selection
    kinds = frozenset(k for k in kinds if k != "cross_flow")
    payload_set = get_payload_set(service, version)
    if not payload_set:
        return {
            "ok": False,
            "error": "payload_set_not_found",
            "selected_api_ids": [],
            "expects": {},
            "warnings": [],
        }
    selected: list[str] = []
    expects: dict[str, int] = {}
    warnings: list[str] = []
    for api_id, entry in (payload_set.get("apis") or {}).items():
        if not isinstance(entry, dict):
            continue
        meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
        ck = str(meta.get("case_kind") or entry.get("name") or "happy").strip().lower()
        if ck == "cross_flow":
            continue
        if ck not in kinds:
            continue
        exp = meta.get("expect_status")
        if exp is None and isinstance(entry.get("response"), dict):
            exp = entry["response"].get("status")
        if ck == "technical" and exp is None:
            warnings.append(f"{api_id}: technical missing expect_status — excluded from k6")
            continue
        selected.append(str(api_id))
        if exp is not None:
            try:
                expects[str(api_id)] = int(exp)
            except (TypeError, ValueError):
                expects[str(api_id)] = 200
        else:
            expects[str(api_id)] = 200
    return {
        "ok": True,
        "service": service,
        "suite": normalize_suite(suite),
        "payload_set_version": int(payload_set.get("version") or 0),
        "selected_api_ids": selected,
        "expects": expects,
        "warnings": warnings,
        "count": len(selected),
    }


def activate_data_gen_set(service: str, profile: str) -> dict[str, Any]:
    row = find_data_gen_payload_set(service, profile)
    if not row:
        return {"ok": False, "error": "data_gen_set_not_found", "service": service, "profile": profile}
    ver = int(row.get("version") or 0)
    set_active_payload_set(service, ver)
    return {"ok": True, "service": service, "profile": profile, "payload_set_version": ver, "label": row.get("label")}


def config_name(service: str, suite: str, environment: str) -> str:
    return f"{service}-{normalize_suite(suite)}-{environment}"


def ensure_suite_config(
    *,
    service: str,
    suite: str,
    environment: str,
    payload_set_version: int,
    selected_api_ids: list[str],
    target_url: str | None = None,
    auth_env: dict[str, Any] | None = None,
    expects: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Upsert an SPT config for this suite run."""
    from specs.load.config_builder import default_config_dict, ensure_default_config
    from specs.persistence.run_store import list_configs, save_config

    name = config_name(service, suite, environment)
    existing = None
    for c in list_configs(service=service, environment=environment) or []:
        if str(c.get("name") or "") == name:
            existing = c
            break
    if existing:
        cfg = dict(existing)
    else:
        try:
            seed = ensure_default_config()
        except Exception:  # noqa: BLE001
            seed = default_config_dict()
        cfg = dict(seed or {})
        cfg.pop("id", None)
    cfg["name"] = name
    cfg["service"] = service
    cfg["environment"] = environment
    cfg["audience"] = cfg.get("audience") or "developer"
    cfg["test_type"] = cfg.get("test_type") or "k6"
    cfg["run_profile"] = "debug"
    cfg["payload_set_version"] = int(payload_set_version)
    cfg["selected_api_ids"] = list(selected_api_ids)
    if target_url:
        cfg["target_url"] = target_url
    payloads = dict(cfg.get("payloads") or {})
    payloads["payload_set_version"] = int(payload_set_version)
    payloads["bench_run"] = {"vus": 1, "iterations": 1}
    if auth_env:
        payloads["auth_env"] = {**(payloads.get("auth_env") or {}), **auth_env}
    if expects:
        payloads["expect_status_by_api"] = dict(expects)
    cfg["payloads"] = payloads
    saved = save_config(cfg)
    return saved if isinstance(saved, dict) else cfg
