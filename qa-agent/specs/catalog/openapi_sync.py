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


def sync_openapi_for_service(
    service: str,
    environment: str | None = None,
    *,
    force: bool = True,
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

    return {
        "ok": False,
        "service": service,
        "environment": env,
        "error": meta.get("error") or "openapi_unavailable",
        "openapi_url": meta.get("openapi_url"),
    }
