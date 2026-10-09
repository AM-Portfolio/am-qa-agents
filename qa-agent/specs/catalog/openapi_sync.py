"""Runtime OpenAPI sync cache — no per-service files in git.

When a service starts feeding and exposes openapi.json, Specs pulls it and
stores under ``{data_dir}/openapi_sync/{service}/{env}.json``. Later loads use
that synced copy if live fetch fails (SPA HTML / transient outage).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from specs.config import settings

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_root() -> Path:
    path = Path(settings.data_dir) / "openapi_sync"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sync_path(service: str, environment: str) -> Path:
    env = (environment or "dev").strip().lower() or "dev"
    d = sync_root() / service
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{env}.json"


def load_synced_openapi(service: str, environment: str) -> dict[str, Any] | None:
    path = sync_path(service, environment)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Synced OpenAPI unreadable %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    doc = data.get("document")
    if not isinstance(doc, dict) or not isinstance(doc.get("paths"), dict):
        return None
    return data


def delete_synced_openapi(service: str, environment: str) -> bool:
    """Remove a poisoned/stale synced document (e.g. another service's OpenAPI)."""
    path = sync_path(service, environment)
    if not path.is_file():
        return False
    try:
        path.unlink()
        logger.info("Deleted synced OpenAPI %s/%s", service, environment)
        return True
    except OSError as exc:
        logger.warning("Could not delete synced OpenAPI %s: %s", path, exc)
        return False


def save_synced_openapi(
    service: str,
    environment: str,
    *,
    document: dict[str, Any],
    openapi_url: str = "",
    target_url: str = "",
    apis: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    env = (environment or "dev").strip().lower() or "dev"
    paths = document.get("paths") if isinstance(document.get("paths"), dict) else {}
    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    record = {
        "service": service,
        "environment": env,
        "synced_at": _now(),
        "openapi_url": openapi_url,
        "target_url": target_url,
        "title": info.get("title"),
        "version": info.get("version"),
        "path_count": len(paths),
        "apis": apis if isinstance(apis, list) else [],
        "document": document,
    }
    path = sync_path(service, env)
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    logger.info(
        "OpenAPI synced for %s/%s paths=%s url=%s",
        service,
        env,
        record["path_count"],
        openapi_url or "(none)",
    )
    return record


def _example_for_param(name: str, raw: Any) -> str:
    if isinstance(raw, str) and raw and not raw.startswith("{{"):
        return raw
    if raw is not None and not isinstance(raw, str):
        return str(raw)
    low = (name or "").lower()
    if "symbol" in low:
        return "RELIANCE"
    if "scheme" in low:
        return "120503"
    if "exchange" in low:
        return "NSE"
    if "date" in low:
        return "2026-01-01"
    if "id" in low or "watchlist" in low:
        return "1"
    return "example"


def document_from_payload_set(
    service: str,
    *,
    version: int | None = None,
    target_url: str = "",
) -> dict[str, Any] | None:
    """Build a minimal OpenAPI 3 document from the active (or given) payload set."""
    import re

    from specs.payloads.payload_store import get_payload_set

    payload_set = get_payload_set(service, version)
    if not payload_set:
        return None
    apis = payload_set.get("apis")
    if not isinstance(apis, dict) or not apis:
        return None

    paths: dict[str, Any] = {}
    for api_id, entry in apis.items():
        if not isinstance(entry, dict):
            continue
        req = entry.get("request") if isinstance(entry.get("request"), dict) else {}
        method = str(req.get("method") or "GET").lower()
        path = str(req.get("path") or "/")
        if not path.startswith("/"):
            path = f"/{path}"
        item = paths.setdefault(path, {})
        params: list[dict[str, Any]] = []
        path_params = req.get("path_params") if isinstance(req.get("path_params"), dict) else {}
        for match in re.finditer(r"\{([^}/]+)\}", path):
            name = match.group(1)
            ex = _example_for_param(name, path_params.get(name))
            params.append(
                {
                    "name": name,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "example": ex},
                }
            )
        query = req.get("query") if isinstance(req.get("query"), dict) else {}
        for qk, qv in query.items():
            schema: dict[str, Any] = {"type": "string"}
            if qv is not None and not (isinstance(qv, str) and str(qv).startswith("{{")):
                schema["example"] = str(qv)
            params.append(
                {"name": str(qk), "in": "query", "required": False, "schema": schema}
            )
        op: dict[str, Any] = {
            "operationId": str(api_id),
            "summary": f"{method.upper()} {path}",
            "parameters": params,
            "responses": {"200": {"description": "OK"}},
        }
        body = req.get("body")
        if body is not None and method in ("post", "put", "patch"):
            op["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"type": "object"},
                        "example": body,
                    }
                },
            }
        item[method] = op

    if not paths:
        return None

    ver = payload_set.get("version")
    label = payload_set.get("label") or f"v{ver}"
    return {
        "openapi": "3.0.1",
        "info": {
            "title": f"{service} (payload set {label})",
            "version": str(ver or "1"),
            "description": (
                "Synthesized from SPT payload set while live OpenAPI is unavailable."
            ),
        },
        "servers": [{"url": target_url.rstrip("/")}] if target_url else [],
        "paths": paths,
    }


def seed_openapi_from_payload_set(
    service: str,
    environment: str | None = None,
    *,
    version: int | None = None,
) -> dict[str, Any]:
    """Persist OpenAPI sync cache from payload set (fallback when live docs 500)."""
    from specs.catalog.catalog_loader import default_target_for_service
    from specs.catalog.openapi_import import openapi_to_apis

    env = (environment or settings.default_environment or "dev").strip().lower() or "dev"
    target = default_target_for_service(service, env) or ""
    doc = document_from_payload_set(service, version=version, target_url=target)
    if not doc:
        return {
            "ok": False,
            "service": service,
            "environment": env,
            "error": "no_payload_set_or_empty",
        }

    # Use the registered live docs URL so poison/belongs checks keep this cache.
    openapi_url = f"{target.rstrip('/')}/v3/api-docs" if target else ""
    apis = openapi_to_apis(doc, include_mutating=True)
    saved = save_synced_openapi(
        service,
        env,
        document=doc,
        openapi_url=openapi_url,
        target_url=target,
        apis=apis,
    )
    saved["source"] = "payload-set"
    # Re-write with source marker for operators
    path = sync_path(service, env)
    try:
        path.write_text(json.dumps(saved, indent=2, default=str), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not re-write payload-set OpenAPI marker: %s", exc)

    return {
        "ok": True,
        "service": service,
        "environment": env,
        "source": "payload-set",
        "path_count": saved.get("path_count"),
        "operation_count": len(apis),
        "openapi_url": openapi_url,
        "synced_at": saved.get("synced_at"),
        "payload_set_version": version,
    }


def seed_openapi_document(
    service: str,
    environment: str | None = None,
    *,
    document: dict[str, Any],
    openapi_url: str = "",
    target_url: str = "",
) -> dict[str, Any]:
    """Persist an explicit OpenAPI document into the sync cache."""
    from specs.catalog.catalog_loader import default_target_for_service
    from specs.catalog.openapi_import import openapi_to_apis

    env = (environment or settings.default_environment or "dev").strip().lower() or "dev"
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        return {"ok": False, "error": "document.paths required"}
    target = target_url or default_target_for_service(service, env) or ""
    url = openapi_url or (f"{target.rstrip('/')}/v3/api-docs" if target else "")
    apis = openapi_to_apis(document, include_mutating=True)
    saved = save_synced_openapi(
        service,
        env,
        document=document,
        openapi_url=url,
        target_url=target,
        apis=apis,
    )
    return {
        "ok": True,
        "service": service,
        "environment": env,
        "source": "seed",
        "path_count": saved.get("path_count"),
        "operation_count": len(apis),
        "openapi_url": url,
        "synced_at": saved.get("synced_at"),
    }


def sync_openapi_for_service(
    service: str,
    environment: str | None = None,
    *,
    force: bool = True,
    allow_payload_set_fallback: bool = True,
) -> dict[str, Any]:
    """Force a live OpenAPI pull + persist. Call when a service starts feeding."""
    from specs.catalog import catalog_loader as cl

    env = (environment or settings.default_environment or "dev").lower()
    if force:
        cl._openapi_doc_cache.pop(f"{service}|{env}", None)

    meta = cl.load_openapi_document(service, env)
    if meta.get("ok") and isinstance(meta.get("document"), dict):
        return {
            "ok": True,
            "service": service,
            "environment": env,
            "source": meta.get("source") or "openapi",
            "path_count": meta.get("path_count"),
            "operation_count": meta.get("operation_count"),
            "openapi_url": meta.get("openapi_url"),
            "synced_at": meta.get("synced_at"),
            "stale": meta.get("source") == "synced-cache",
            "live_error": meta.get("live_error"),
        }

    synced = load_synced_openapi(service, env)
    if synced:
        return {
            "ok": True,
            "service": service,
            "environment": env,
            "source": "synced-cache",
            "path_count": synced.get("path_count"),
            "openapi_url": synced.get("openapi_url"),
            "synced_at": synced.get("synced_at"),
            "stale": True,
            "live_error": meta.get("error"),
        }

    if allow_payload_set_fallback:
        seeded = seed_openapi_from_payload_set(service, env)
        if seeded.get("ok"):
            cl._openapi_doc_cache.pop(f"{service}|{env}", None)
            return seeded

    return {
        "ok": False,
        "service": service,
        "environment": env,
        "error": meta.get("error") or "openapi_unavailable",
        "openapi_url": meta.get("openapi_url"),
    }
