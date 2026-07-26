from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from specs.config import settings


def artifact_dir(run_id: str) -> Path:
    path = Path(settings.data_dir) / "artifacts" / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_artifact(run_id: str, name: str, data: bytes) -> str:
    path = artifact_dir(run_id) / name
    path.write_bytes(data)
    return str(path)


def read_artifact(run_id: str, name: str) -> bytes | None:
    path = artifact_dir(run_id) / name
    if path.is_file():
        return path.read_bytes()
    return None


def artifact_exists(run_id: str, name: str) -> bool:
    return (artifact_dir(run_id) / name).is_file()


def _content_type_for(name: str) -> str:
    n = name.lower()
    if n.endswith(".html"):
        return "text/html; charset=utf-8"
    if n.endswith(".json"):
        return "application/json"
    if n.endswith(".pdf"):
        return "application/pdf"
    if n.endswith(".zip"):
        return "application/zip"
    if n.endswith(".png"):
        return "image/png"
    if n.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "application/octet-stream"


async def upload_to_minio(key: str, data: bytes, content_type: str = "application/json") -> str | None:
    if not settings.minio_access_key or not settings.minio_secret_key:
        return None
    url = f"{settings.minio_endpoint.rstrip('/')}/{settings.minio_bucket}/{key}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.put(
                url,
                content=data,
                headers={
                    "Content-Type": content_type,
                },
                auth=(settings.minio_access_key, settings.minio_secret_key),
            )
            if r.status_code < 300:
                return f"{settings.minio_public_console_url.rstrip('/')}/browser/{settings.minio_bucket}/{key}"
    except Exception:
        return None
    return None


async def download_from_minio(key: str) -> bytes | None:
    if not settings.minio_access_key or not settings.minio_secret_key or not key:
        return None
    url = f"{settings.minio_endpoint.rstrip('/')}/{settings.minio_bucket}/{key.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(
                url,
                auth=(settings.minio_access_key, settings.minio_secret_key),
            )
            if r.status_code == 200:
                return r.content
    except Exception:
        return None
    return None


async def persist_run_artifacts(
    run_id: str,
    service: str,
    files: dict[str, bytes],
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    prefix = f"{service or 'unknown'}/{run_id}"
    for name, data in files.items():
        local = save_artifact(run_id, name, data)
        entry: dict[str, Any] = {"name": name, "local_path": local, "size": len(data)}
        ctype = _content_type_for(name)
        minio_url = await upload_to_minio(f"{prefix}/{name}", data, content_type=ctype)
        if minio_url:
            entry["minio_url"] = minio_url
            entry["minio_key"] = f"{prefix}/{name}"
        artifacts.append(entry)
    return artifacts


def portal_artifact_url(run_id: str, name: str) -> str:
    """Relative artifact URL for the portal (no ROOT_PATH — apiBase already has it)."""
    return f"/api/runs/{run_id}/artifacts/{name}"
