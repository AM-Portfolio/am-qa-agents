"""Batch data-gen import (service × profile) for MCP / REST — continue on failure."""
from __future__ import annotations

from typing import Any

from specs.data_gen.import_svc import import_data_gen
from specs.payloads.zip_codec import ZipCodecError, maybe_expand_import_fields


def _normalize_item(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("each batch item must be an object")
    service = str(raw.get("service") or "").strip()
    if not service:
        raise ValueError("service required")
    profile = str(raw.get("profile") or "default").strip() or "default"
    environment = str(raw.get("environment") or "dev").strip() or "dev"
    make_active = bool(raw.get("make_active", True))
    sync_workflows = bool(raw.get("sync_workflows", True))
    pack_path = raw.get("pack_path")
    pack_path_s = str(pack_path).strip() if pack_path else None

    try:
        expanded = maybe_expand_import_fields(dict(raw))
    except ZipCodecError as exc:
        raise ValueError(str(exc)) from exc

    payload_set = expanded.get("payload_set")
    collection = expanded.get("collection")
    env = expanded.get("env")
    # Accept bare payload_set_json string field
    ps_json = raw.get("payload_set_json")
    if payload_set is None and isinstance(ps_json, str) and ps_json.strip():
        import json

        payload_set = json.loads(ps_json)
    if payload_set is None and isinstance(raw.get("payload_set"), dict):
        payload_set = raw["payload_set"]

    body = None
    if payload_set is not None or collection is not None or env is not None:
        body = {
            "payload_set": payload_set if isinstance(payload_set, dict) else None,
            "collection": collection if isinstance(collection, dict) else None,
            "env": env if isinstance(env, dict) else None,
            "label": expanded.get("label") or raw.get("label"),
        }
    return {
        "service": service,
        "profile": profile,
        "environment": environment,
        "body": body,
        "pack_path": pack_path_s,
        "make_active": make_active,
        "sync_workflows": sync_workflows,
    }


def import_one_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Import a single batch item. Always returns a result dict with ok/service/profile."""
    try:
        norm = _normalize_item(raw)
    except (ValueError, TypeError, ZipCodecError) as exc:
        return {
            "ok": False,
            "error": "invalid_item",
            "message": str(exc),
            "service": str((raw or {}).get("service") or "") if isinstance(raw, dict) else "",
            "profile": str((raw or {}).get("profile") or "") if isinstance(raw, dict) else "",
        }
    out = import_data_gen(
        service=norm["service"],
        profile=norm["profile"],
        environment=norm["environment"],
        body=norm["body"],
        pack_path=norm["pack_path"],
        make_active=norm["make_active"],
        sync_workflows=norm["sync_workflows"],
    )
    return {
        **out,
        "service": norm["service"],
        "profile": out.get("profile") or norm["profile"],
        "payload_set_version": out.get("payload_set_version"),
    }


def import_batch(
    items: list[Any] | None,
    *,
    default_environment: str = "dev",
) -> dict[str, Any]:
    """Sequential import; continue on failure. Returns per-item results."""
    rows = list(items or [])
    if not rows:
        return {
            "ok": False,
            "error": "items_required",
            "message": "items must be a non-empty list",
            "results": [],
            "count": 0,
            "ok_count": 0,
            "fail_count": 0,
        }
    results: list[dict[str, Any]] = []
    for raw in rows:
        item = dict(raw) if isinstance(raw, dict) else raw
        if isinstance(item, dict) and not item.get("environment"):
            item = {**item, "environment": default_environment}
        results.append(import_one_item(item if isinstance(item, dict) else {}))
    ok_count = sum(1 for r in results if r.get("ok"))
    fail_count = len(results) - ok_count
    return {
        "ok": fail_count == 0 and ok_count > 0,
        "results": results,
        "count": len(results),
        "ok_count": ok_count,
        "fail_count": fail_count,
        "payload_set_versions": {
            f"{r.get('service')}:{r.get('profile')}": r.get("payload_set_version")
            for r in results
            if r.get("ok")
        },
    }
