"""LLM gate + secret redaction — ≤3 calls/run via LiteLLM / OpenAI-compat."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|password|secret|token|authorization)\s*[:=]\s*['\"]?[^\s'\"]{6,}"
)
_PEM_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----")
_AWS_RE = re.compile(r"AKIA[0-9A-Z]{16}")


def redact_secrets(text: str) -> str:
    out = _PEM_RE.sub("[REDACTED_PRIVATE_KEY]", text or "")
    out = _AWS_RE.sub("[REDACTED_AWS_KEY]", out)
    out = _SECRET_RE.sub(r"\1=[REDACTED]", out)
    return out


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_secrets(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj


class GatedLlmClient:
    """
    Budgeted LLM client.

    Uses LiteLLM OpenAI-compat (`LITELLM_BASE_URL` + `LITELLM_MASTER_KEY`) when enabled.
    """

    def __init__(self, *, max_calls: int | None = None) -> None:
        self.max_calls = max_calls or int(os.getenv("QA_AGENT_LLM_MAX_CALLS", "3"))
        self._calls = 0
        self.enabled = os.getenv("QA_AGENT_LLM_ENABLED", "").lower() in {"1", "true", "yes"}

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self._calls)

    def complete_json(
        self,
        *,
        prompt_name: str,
        inputs: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        safe = redact_obj(inputs)
        if not self.enabled or self._calls >= self.max_calls:
            return {
                **fallback,
                "llm_used": False,
                "mode": "budget_exhausted" if self._calls >= self.max_calls else "disabled",
                "prompt_name": prompt_name,
            }
        self._calls += 1

        api_key = (
            os.getenv("QA_AGENT_LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("LITELLM_MASTER_KEY")
            or ""
        )
        base = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("LITELLM_BASE_URL")
            or ""
        ).rstrip("/")
        model = (
            os.getenv("QA_AGENT_LLM_MODEL")
            or os.getenv("LLM_MODEL")
            or "Qwen/Qwen3-VL-8B-Instruct"
        )

        if not api_key or not base:
            return {
                **fallback,
                "llm_used": False,
                "mode": "template_llm_placeholder",
                "prompt_name": prompt_name,
                "langfuse_host": os.getenv("LANGFUSE_HOST"),
                "note": "Missing LITELLM_BASE_URL / API key",
                "redacted_input_keys": list(safe.keys()) if isinstance(safe, dict) else [],
            }

        system = (
            f"You are qa-agent prompt `{prompt_name}`. "
            "Return a single JSON object only (no markdown). "
            "Merge improvements into the provided fallback fields."
        )
        user = json.dumps({"inputs": safe, "fallback": fallback}, ensure_ascii=False)[:12000]
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"{base}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                    },
                )
                if resp.status_code >= 400:
                    return {
                        **fallback,
                        "llm_used": False,
                        "mode": "fallback_template",
                        "llm_error_mode": "llm_http_error",
                        "prompt_name": prompt_name,
                        "http_status": resp.status_code,
                        "note": resp.text[:300],
                    }
                data = resp.json()
                content = (
                    ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}"
                )
                parsed = json.loads(content) if isinstance(content, str) else {}
                if not isinstance(parsed, dict):
                    parsed = {"raw": parsed}
                out = {**fallback, **parsed}
                out["llm_used"] = True
                out["mode"] = "litellm"
                out["prompt_name"] = prompt_name
                out["model"] = model
                out["langfuse_host"] = os.getenv("LANGFUSE_HOST")
                return out
        except Exception as exc:  # noqa: BLE001
            return {
                **fallback,
                "llm_used": False,
                "mode": "fallback_template",
                "llm_error_mode": "llm_error",
                "prompt_name": prompt_name,
                "note": str(exc)[:300],
            }


_CLIENT: GatedLlmClient | None = None


def get_llm_client() -> GatedLlmClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = GatedLlmClient()
    return _CLIENT
