"""Upload Asrax release-ops pack to the shared MinIO instance (not am-infra Drive)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def endpoint() -> str:
    return (
        os.getenv("QA_AGENT_MINIO_ENDPOINT")
        or os.getenv("MINIO_ENDPOINT")
        or "https://minio.asrax.in"
    ).rstrip("/")


def console_url() -> str:
    return (
        os.getenv("MINIO_PUBLIC_CONSOLE_URL")
        or os.getenv("MINIO_CONSOLE_URL")
        or "https://minio-console.asrax.in"
    ).rstrip("/")


def bucket() -> str:
    return (
        os.getenv("QA_AGENT_MINIO_BUCKET")
        or os.getenv("MINIO_BUCKET")
        or "qa-agent"
    ).strip()


def _auth() -> tuple[str, str] | None:
    ak = (
        os.getenv("QA_AGENT_MINIO_ACCESS_KEY")
        or os.getenv("MINIO_ACCESS_KEY")
        or ""
    ).strip()
    sk = (
        os.getenv("QA_AGENT_MINIO_SECRET_KEY")
        or os.getenv("MINIO_SECRET_KEY")
        or ""
    ).strip()
    if not ak or not sk:
        return None
    return ak, sk


def stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")


def day(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def year(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y")


def object_prefix(*, triggered_at: datetime, release_id: str) -> str:
    """Path under bucket — separate from am-infra Asrax/Releases Drive layout."""
    return f"asrax-release-ops/{year(triggered_at)}/{day(triggered_at)}/{release_id}"


def dated_object_name(
    *,
    release_id: str,
    triggered_stamp: str,
    workflow_stamp: str,
    stem: str,
    suffix: str,
) -> str:
    return (
        f"{release_id}_triggered-{triggered_stamp}_workflow-{workflow_stamp}_{stem}{suffix}"
    )


def browser_url(key: str, *, buck: str | None = None) -> str:
    b = buck or bucket()
    return f"{console_url()}/browser/{b}/{key.lstrip('/')}"


def _s3_client():
    auth = _auth()
    if not auth:
        raise RuntimeError("MINIO_ACCESS_KEY / MINIO_SECRET_KEY not set")
    try:
        import boto3
        from botocore.client import Config
    except ImportError as exc:
        raise RuntimeError("boto3 required for MinIO SigV4: pip install boto3") from exc
    return boto3.client(
        "s3",
        endpoint_url=endpoint(),
        aws_access_key_id=auth[0],
        aws_secret_access_key=auth[1],
        config=Config(signature_version="s3v4"),
        region_name=os.getenv("MINIO_REGION") or "us-east-1",
    )


def ensure_bucket(s3: Any, buck: str) -> None:
    try:
        s3.head_bucket(Bucket=buck)
    except Exception:
        s3.create_bucket(Bucket=buck)


def put_bytes(
    *,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    buck: str | None = None,
) -> dict[str, Any]:
    try:
        s3 = _s3_client()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "key": key}
    b = buck or bucket()
    try:
        ensure_bucket(s3, b)
        s3.put_object(Bucket=b, Key=key.lstrip("/"), Body=data, ContentType=content_type)
        return {
            "ok": True,
            "status": 200,
            "bucket": b,
            "key": key,
            "bytes": len(data),
            "browser_url": browser_url(key, buck=b),
            "object_url": f"{endpoint()}/{b}/{key.lstrip('/')}",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "key": key}


def put_file(
    *,
    local_path: Path,
    key: str,
    content_type: str,
    buck: str | None = None,
) -> dict[str, Any]:
    return put_bytes(
        key=key,
        data=local_path.read_bytes(),
        content_type=content_type,
        buck=buck,
    )


def mime_for(path: Path) -> str:
    suf = path.suffix.lower()
    if suf == ".pdf":
        return "application/pdf"
    if suf == ".png":
        return "image/png"
    if suf in {".html", ".htm"}:
        return "text/html"
    if suf == ".md":
        return "text/markdown"
    if suf == ".json":
        return "application/json"
    return "application/octet-stream"


def upload_release_pack(
    *,
    pack: Path,
    release_id: str,
    triggered_at: datetime,
    workflow_started_at: datetime,
) -> dict[str, Any]:
    """Upload pack once to MinIO under asrax-release-ops/{year}/{day}/{release_id}/."""
    trig = stamp(triggered_at)
    wf = stamp(workflow_started_at)
    prefix = object_prefix(triggered_at=triggered_at, release_id=release_id)
    links: dict[str, str] = {
        "folder": f"{console_url()}/browser/{bucket()}/{prefix}/",
        "prefix": prefix,
        "bucket": bucket(),
    }
    uploads: list[tuple[str, str, str]] = [
        ("master_pdf", "master-release-report.pdf", "master-release-report"),
        ("master_html", "master-release-report.html", "master-release-report"),
        ("summary", "summary.json", "summary"),
        ("ui_summary", "summary.json", "ui-summary"),
        ("stability", "final/stability-score.json", "stability-score"),
        ("cliq_message", "final/cliq-message.md", "cliq-message"),
    ]
    ui_dir = pack / "ui"
    if ui_dir.is_dir():
        for path in sorted(ui_dir.glob("suite-*.json")):
            uploads.append((f"ui_{path.stem}", f"ui/{path.name}", path.stem))
        for path in sorted(ui_dir.rglob("*.png"))[:40]:
            rel = path.relative_to(pack).as_posix()
            uploads.append((f"shot_{path.stem}"[:80], rel, f"shot-{path.stem}"[:60]))

    errors: list[str] = []
    for key_name, rel, stem in uploads:
        path = pack / rel
        if not path.is_file():
            continue
        obj_name = dated_object_name(
            release_id=release_id,
            triggered_stamp=trig,
            workflow_stamp=wf,
            stem=stem,
            suffix=path.suffix,
        )
        key = f"{prefix}/{obj_name}"
        result = put_file(local_path=path, key=key, content_type=mime_for(path))
        if result.get("ok"):
            links[key_name] = str(result.get("browser_url") or "")
            if key_name == "master_pdf":
                links["final_pdf"] = links[key_name]
        else:
            errors.append(f"{key}: {result.get('error') or result.get('status')}")

    manifest = {
        "release_id": release_id,
        "prefix": prefix,
        "triggered_at": triggered_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workflow_started_at": workflow_started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "links": {k: v for k, v in links.items() if k not in {"prefix", "bucket"}},
        "store": "minio",
        "endpoint": endpoint(),
        "bucket": bucket(),
    }
    man_name = dated_object_name(
        release_id=release_id,
        triggered_stamp=trig,
        workflow_stamp=wf,
        stem="pack-manifest",
        suffix=".json",
    )
    man_key = f"{prefix}/{man_name}"
    man_put = put_bytes(
        key=man_key,
        data=json.dumps(manifest, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    if man_put.get("ok"):
        links["manifest"] = str(man_put.get("browser_url") or "")
    else:
        errors.append(f"manifest: {man_put.get('error') or man_put.get('status')}")

    return {
        "ok": not errors,
        "store": "minio",
        "prefix": prefix,
        "links": links,
        "errors": errors,
    }
