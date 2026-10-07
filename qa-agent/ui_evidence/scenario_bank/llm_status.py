"""LiteLLM availability probe for scenario-bank invent (Phase 0 / MCP)."""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return (
        os.getenv("LITELLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "http://localhost:4000"
    ).rstrip("/")


def _api_key() -> str:
    return (
        os.getenv("LITELLM_MASTER_KEY")
        or os.getenv("QA_AGENT_LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()


def _planner_model() -> str:
    return (
        os.getenv("QA_AGENT_LLM_MODEL")
        or os.getenv("LLM_MODEL")
        or os.getenv("LLM_PLANNER_MODEL")
        or "deepseek-chat"
    ).strip()


def probe_litellm(
    *,
    ping_chat: bool = False,
    timeout: float = 15.0,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """
    Probe LiteLLM proxy used by qa-agent invent.

    Returns available=true only when key is set and /models (or /v1/models) succeeds.
    Optional ping_chat runs a tiny completion (spend); default off for Phase 0.
    Never returns the API key.
    """
    url = (base_url or _base_url()).rstrip("/")
    key = api_key if api_key is not None else _api_key()
    model_id = (model or _planner_model()).strip()

    out: dict[str, Any] = {
        "provider": "litellm",
        "base_url": url,
        "key_configured": bool(key),
        "available": False,
        "model": model_id,
        "models_sample": [],
        "models_count": 0,
        "ping_chat": False,
        "error": None,
    }
    if not key:
        out["error"] = "LITELLM_MASTER_KEY unset"
        return out

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    models_paths = (f"{url}/v1/models", f"{url}/models")
    last_err = "no_response"
    try:
        with httpx.Client(timeout=timeout) as client:
            data = None
            for path in models_paths:
                resp = client.get(path, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    out["models_endpoint"] = path
                    break
                last_err = f"HTTP {resp.status_code} {path}"
            if data is None:
                out["error"] = last_err
                return out

            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                rows = []
            ids = [str(r.get("id") or r.get("model") or "") for r in rows if isinstance(r, dict)]
            ids = [i for i in ids if i]
            out["models_count"] = len(ids)
            out["models_sample"] = ids[:12]
            out["available"] = True

            if ping_chat:
                chat_url = f"{url}/v1/chat/completions"
                if "/v1/" not in (out.get("models_endpoint") or ""):
                    chat_url = f"{url}/chat/completions"
                payload = {
                    "model": model_id,
                    "messages": [
                        {"role": "user", "content": "Reply with exactly: ok"},
                    ],
                    "max_tokens": 8,
                    "temperature": 0,
                }
                cresp = client.post(chat_url, headers=headers, json=payload)
                if cresp.status_code != 200:
                    out["available"] = False
                    out["error"] = f"chat HTTP {cresp.status_code}: {cresp.text[:200]}"
                    return out
                body = cresp.json()
                content = (
                    ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
                    or ""
                )
                out["ping_chat"] = True
                out["ping_preview"] = str(content)[:80]
    except Exception as exc:  # noqa: BLE001
        logger.warning("litellm probe failed: %s", exc)
        out["error"] = str(exc)
        out["available"] = False
    return out
