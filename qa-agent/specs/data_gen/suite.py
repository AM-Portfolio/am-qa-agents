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


def _variant_api_id(base_api_id: str, variant: dict[str, Any], index: int) -> str:
    meta = variant.get("meta") if isinstance(variant.get("meta"), dict) else {}
    vid = (
        str(variant.get("variant_id") or meta.get("variant_id") or variant.get("name") or index)
        .strip()
        .replace(" ", "_")
    )
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in vid) or str(index)
    return f"{base_api_id}__v__{safe}"


def _expect_of(entry: dict[str, Any], meta: dict[str, Any]) -> Any:
    exp = meta.get("expect_status")
    if exp is None and entry.get("expect_status") is not None:
        exp = entry.get("expect_status")
    if exp is None and isinstance(entry.get("response"), dict):
        exp = entry["response"].get("status")
    return exp


def _consider_row(
    *,
    api_id: str,
    entry: dict[str, Any],
    kinds: frozenset[str],
    selected: list[str],
    expects: dict[str, int],
    warnings: list[str],
) -> None:
    meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
    ck = str(
        meta.get("case_kind") or entry.get("case_kind") or entry.get("name") or "happy"
    ).strip().lower()
    if ck == "cross_flow":
        return
    if ck not in kinds:
        return
    exp = _expect_of(entry, meta)
    if ck == "technical" and exp is None:
        warnings.append(f"{api_id}: technical missing expect_status — excluded from k6")
        return
    selected.append(str(api_id))
    if exp is not None:
        try:
            expects[str(api_id)] = int(exp)
        except (TypeError, ValueError):
            expects[str(api_id)] = 200
    else:
        expects[str(api_id)] = 200


def api_ids_for_suite(
    service: str,
    suite: str,
    *,
    version: int | None = None,
    case_kinds: list[str] | None = None,
    materialize_variants: bool = False,
) -> dict[str, Any]:
    """Select api_ids whose primary or variant meta.case_kind is in suite filter.

    When materialize_variants=True, matching meta.variants are upserted as
    ``{api_id}__v__{variant_id}`` rows so k6 can execute them.
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
    ver = int(payload_set.get("version") or 0)
    selected: list[str] = []
    expects: dict[str, int] = {}
    warnings: list[str] = []
    materialized: list[str] = []

    for api_id, entry in (payload_set.get("apis") or {}).items():
        if not isinstance(entry, dict):
            continue
        # Skip already-materialized variant rows when walking primaries' variants
        meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
        if meta.get("materialized_from"):
            _consider_row(
                api_id=str(api_id),
                entry=entry,
                kinds=kinds,
                selected=selected,
                expects=expects,
                warnings=warnings,
            )
            continue

        _consider_row(
            api_id=str(api_id),
            entry=entry,
            kinds=kinds,
            selected=selected,
            expects=expects,
            warnings=warnings,
        )

        variants = meta.get("variants") or []
        if not isinstance(variants, list):
            continue
        for idx, var in enumerate(variants):
            if not isinstance(var, dict):
                continue
            vmeta = dict(var.get("meta") or {}) if isinstance(var.get("meta"), dict) else {}
            if var.get("case_kind") and not vmeta.get("case_kind"):
                vmeta["case_kind"] = var["case_kind"]
            if var.get("expect_status") is not None and vmeta.get("expect_status") is None:
                vmeta["expect_status"] = var["expect_status"]
            if var.get("variant_id") and not vmeta.get("variant_id"):
                vmeta["variant_id"] = var["variant_id"]
            vck = str(vmeta.get("case_kind") or var.get("case_kind") or "").strip().lower()
            if not vck or vck == "cross_flow" or vck not in kinds:
                continue
            syn_id = _variant_api_id(str(api_id), var, idx)
            v_entry = {
                "api_id": syn_id,
                "name": var.get("name") or vmeta.get("variant_id") or syn_id,
                "request": var.get("request") or {},
                "response": var.get("response") or {},
                "meta": {
                    **vmeta,
                    "materialized_from": str(api_id),
                    "case_kind": vck,
                },
                "case_kind": vck,
                "expect_status": vmeta.get("expect_status") or var.get("expect_status"),
            }
            if materialize_variants:
                from specs.payloads.payload_store import upsert_api_in_payload_set

                upsert_api_in_payload_set(
                    service,
                    syn_id,
                    version=ver,
                    request=v_entry.get("request") if isinstance(v_entry.get("request"), dict) else {},
                    response=v_entry.get("response") if isinstance(v_entry.get("response"), dict) else {},
                    meta=v_entry["meta"],
                    name=str(v_entry.get("name") or "variant"),
                    bump_set=False,
                )
                materialized.append(syn_id)
            _consider_row(
                api_id=syn_id,
                entry=v_entry,
                kinds=kinds,
                selected=selected,
                expects=expects,
                warnings=warnings,
            )

    # Dedupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for aid in selected:
        if aid not in seen:
            seen.add(aid)
            unique.append(aid)

    return {
        "ok": True,
        "service": service,
        "suite": normalize_suite(suite),
        "payload_set_version": ver,
        "selected_api_ids": unique,
        "expects": expects,
        "warnings": warnings,
        "count": len(unique),
        "materialized_api_ids": materialized,
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
