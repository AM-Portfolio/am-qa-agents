"""Pluggable collection import → AmImportBundle → payload sets."""
from __future__ import annotations

from typing import Any

from specs.import_adapters.base import AmImportBundle, merge_bundle_env  # noqa: F401 — re-export
from specs.import_adapters.registry import get_adapter, list_formats
from specs.payloads.payload_store import create_payload_set, upsert_api_in_payload_set


def import_collection_to_payload_set(
    *,
    service: str,
    collection: Any,
    environment: Any | None = None,
    format: str | None = None,
    label: str | None = None,
    make_active: bool = True,
    bump_set: bool = True,
) -> dict[str, Any]:
    """Parse vendor collection (+ optional env) and write into a service payload set."""
    adapter = get_adapter(format, raw=collection)
    bundle = adapter.parse_collection(collection, service=service)
    env: dict[str, str] = {}
    if environment is not None:
        env = adapter.parse_environment(environment)
    bundle = merge_bundle_env(bundle, env)
    if label and label.strip():
        bundle.label = label.strip()

    if bump_set:
        payload_set = create_payload_set(
            service,
            label=bundle.label or f"import-{bundle.source}",
            make_active=make_active,
            empty=True,
        )
        version = int(payload_set.get("version") or 1)
    else:
        from specs.payloads.payload_store import ensure_payload_set

        payload_set = ensure_payload_set(service, label=bundle.label or "working")
        version = int(payload_set.get("version") or 1)

    imported = 0
    skipped = 0
    warnings = list(bundle.warnings)
    for item in bundle.items:
        if not item.method or not item.path:
            skipped += 1
            continue
        request = {
            "method": item.method,
            "path": item.path,
            "path_params": item.path_params,
            "query": item.query,
            "headers": item.headers,
            "body": item.body,
        }
        extra_meta = getattr(item, "extra_meta", None)
        meta: dict[str, Any] = {
            "source": f"import:{bundle.source}",
            "name": item.name,
            "auth_hint": item.auth_hint,
        }
        if isinstance(extra_meta, dict):
            meta.update(extra_meta)
        extra_resp = getattr(item, "extra_response", None)
        response = dict(extra_resp) if isinstance(extra_resp, dict) else {}
        upsert_api_in_payload_set(
            service,
            item.api_id,
            version=version,
            request=request,
            response=response,
            meta=meta,
            name=str((extra_meta or {}).get("case_kind") or "imported")
            if isinstance(extra_meta, dict)
            else "imported",
            bump_set=False,
        )
        imported += 1

    # Persist env keys onto set meta via a sentinel api is overkill; return env for caller
    return {
        "ok": imported > 0,
        "service": service,
        "format": adapter.format_id,
        "label": bundle.label,
        "payload_set_version": version,
        "imported": imported,
        "skipped": skipped,
        "warnings": warnings,
        "env": dict(bundle.env),
        "formats_available": list_formats(),
        "bundle_preview": {
            "item_count": len(bundle.items),
            "env_keys": sorted(bundle.env.keys()),
        },
    }


__all__ = [
    "AmImportBundle",
    "get_adapter",
    "import_collection_to_payload_set",
    "list_formats",
    "merge_bundle_env",
]
