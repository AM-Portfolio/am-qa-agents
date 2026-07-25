"""Document store — local + tool-agent document.put → MinIO."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from adapters.mcp_fallback import a2a_execute
from adapters.specialists import load_agent_base_url


async def store_document(
    *,
    tracking_id: str,
    local_path: str,
    content_type: str = "text/html",
    tool_agent_base_url: str | None = None,
) -> dict[str, Any]:
    """
    Prefer tool-agent document.put when configured; else return file:// ref.
    """
    store_via = (os.getenv("QA_AGENT_PDF_STORE") or "local").lower()
    path = Path(local_path)
    if not path.is_file():
        return {"ok": False, "error": "missing_file", "pdf_docs_ref": None}

    if store_via in {"local", "file"}:
        return {
            "ok": True,
            "pdf_docs_ref": f"file://{path.resolve()}",
            "store": "local",
            "path": str(path.resolve()),
        }

    if os.getenv("QA_AGENT_SKIP_DOCUMENT_STORE", "").lower() in {"1", "true", "yes"}:
        return {
            "ok": True,
            "pdf_docs_ref": f"file://{path.resolve()}",
            "store": "skipped",
            "path": str(path.resolve()),
        }

    base = (tool_agent_base_url or load_agent_base_url("tool-agent")).rstrip("/")
    body = path.read_bytes()
    a2a = await a2a_execute(
        capability="document.put",
        payload={
            "bucket_prefix": f"qa-agent/{tracking_id}",
            "filename": path.name,
            "content_type": content_type,
            "content_b64": base64.b64encode(body).decode("ascii"),
        },
        base_url=base,
        read_only=False,
    )
    if not a2a.get("ok"):
        return {
            "ok": False,
            "store": "document.put",
            "http_status": a2a.get("http_status"),
            "pdf_docs_ref": f"file://{path.resolve()}",
            "fallback": "local",
            "error": a2a.get("error"),
            "mode": "fallback_template",
        }
    data = a2a.get("data") if isinstance(a2a.get("data"), dict) else {}
    ref = (
        data.get("docs_ref")
        or data.get("url")
        or f"minio://qa-agent/{tracking_id}/{path.name}"
    )
    return {
        "ok": True,
        "store": "document.put",
        "mode": "fallback_mcp",
        "pdf_docs_ref": ref,
        "signed_url": data.get("signed_url"),
    }
