"""Onboard prep step/report schema + smoke failure classification + latest.json persist."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# Required = fail-fast when ok=False (unless hard_fail overrides for soft steps).
REQUIRED_STEPS: dict[str, bool] = {
    "analyze": True,
    "openapi_sync": True,
    "apis_catalog": True,
    "tools_refresh": True,
    "contract": True,
    "auth_try_token": True,
    "prepare_mcp": False,
    "import_data_gen": False,
    "generate_all_payloads": True,
    "llm_fallback": False,
    "tools_smoke": False,
    "overview_report": False,
}


def normalize_env(environment: str | None) -> str:
    e = (environment or "dev").strip().lower()
    return "dev" if e == "dig" else e


def make_step(
    step: str,
    *,
    ok: bool,
    status: str,
    error: str | None = None,
    evidence: dict[str, Any] | None = None,
    duration_ms: int = 0,
    hard_fail: bool | None = None,
) -> dict[str, Any]:
    """Uniform OnboardStep object for Temporal UI + Specs poll."""
    required = REQUIRED_STEPS.get(step, True)
    if hard_fail is None:
        hard_fail = bool(required and not ok)
    return {
        "step": step,
        "ok": bool(ok),
        "status": status,
        "error": error,
        "evidence": evidence or {},
        "duration_ms": int(duration_ms),
        "required": required,
        "hard_fail": bool(hard_fail),
    }


def timed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def classify_smoke_failure(
    result: dict[str, Any] | None,
    *,
    strict_smoke: bool = False,
) -> tuple[bool, str, str]:
    """Classify tools_smoke failure.

    Returns (hard_fail, status, short_error).
    - auth / JWKS / identity → hard
    - LAGO_API_ERROR / business NOT_FOUND → soft (billing_dependency)
    - strict_smoke=True → any failure hard
    """
    r = result or {}
    status_code = int(r.get("status") or r.get("http_status") or 0)
    err = str(r.get("error") or "")
    body = r.get("body")
    if isinstance(body, dict):
        body_s = json.dumps(body, default=str)
        code = str(body.get("code") or body.get("error") or body.get("errorCode") or "")
    else:
        body_s = str(body or "")
        code = ""
    combined = f"{err} {body_s} {code}".lower()

    if any(
        x in combined
        for x in (
            "jwks",
            "kid",
            "signing key",
            "signature verification",
            "jwt",
            "token invalid",
            "unauthorized",
        )
    ) or status_code == 401:
        return True, "auth_jwks_mismatch", err or f"http_{status_code or 401}"

    if "identity" in combined and any(
        x in combined for x in ("unavailable", "failed", "timeout", "connection")
    ):
        return True, "identity_unavailable", err or "identity_unavailable"

    if (
        "lago_api_error" in combined
        or "lago" in combined
        or (status_code >= 500 and "billing" in combined)
    ):
        return False, "billing_dependency", err or "LAGO_API_ERROR"

    if "not_found" in combined or status_code == 404:
        return False, "billing_dependency", err or "NOT_FOUND"

    if strict_smoke:
        return True, "smoke_failed", err or f"http_{status_code or 'error'}"

    return False, "smoke_soft_failure", err or f"http_{status_code or 'error'}"


def _norm_slash_path(path: str) -> str:
    p = (path or "").strip() or "/"
    if not p.startswith("/"):
        p = f"/{p}"
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/")
    return p


def _collapse_path_params(path: str) -> str:
    """Normalize `{user_id}` and concrete substituted segments to `{}` for parity."""
    import re

    p = _norm_slash_path(path)
    # Already-templated segments
    p = re.sub(r"\{[^/]+\}", "{}", p)
    parts: list[str] = []
    for seg in p.split("/"):
        if seg in ("", "{}"):
            parts.append(seg)
            continue
        # UUID / long hex ids
        if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", seg):
            parts.append("{}")
            continue
        if re.fullmatch(r"[0-9a-fA-F-]{16,}", seg):
            parts.append("{}")
            continue
        # email / username.with.dot / obvious seed values from payload overlays
        if "@" in seg or ("." in seg and not seg.startswith(".")) or seg.lower() in {
            "example",
            "test",
            "demo",
            "sample",
        }:
            parts.append("{}")
            continue
        # Concrete user/resource ids from payload overlays (e.g. ssd2658) — keep
        # static route words (admin, users, roles, openapi, v1, …) literal.
        if re.fullmatch(r"[A-Za-z]*\d[\w-]*", seg) and seg.lower() not in {
            "v1",
            "v2",
            "v3",
            "2fa",
        }:
            parts.append("{}")
            continue
        parts.append(seg)
    return "/".join(parts) if parts else "/"


def path_template_key(method: Any, path: Any) -> str:
    """Normalize method+path for APIs↔tools parity (template form)."""
    m = str(method or "").upper().strip()
    return f"{m} {_collapse_path_params(str(path or ''))}"


def apis_tools_parity(
    apis: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare method+path sets between Specs APIs and OpenAPI tools."""
    api_keys = {
        path_template_key(
            a.get("method"),
            a.get("path_template") or a.get("path"),
        )
        for a in apis
        if isinstance(a, dict)
    }
    tool_keys = {
        path_template_key(t.get("method"), t.get("path") or t.get("operation_path"))
        for t in tools
        if isinstance(t, dict)
    }
    # Ignore pure health convention when comparing real ops
    def _real(keys: set[str]) -> set[str]:
        return {
            k
            for k in keys
            if k
            and "/health" not in k.lower()
            and "/actuator/health" not in k.lower()
        }

    api_r, tool_r = _real(api_keys), _real(tool_keys)
    missing_tools = sorted(api_r - tool_r)
    extra_tools = sorted(tool_r - api_r)
    ok = not missing_tools and len(api_r) > 0 and len(tool_r) > 0
    return {
        "ok": ok,
        "api_count": len(api_r),
        "tool_count": len(tool_r),
        "missing_tools": missing_tools[:40],
        "extra_tools": extra_tools[:40],
    }


def onboard_report_dir(data_dir: str, service: str, environment: str) -> Path:
    return Path(data_dir) / "onboard" / service / normalize_env(environment)


def persist_latest_report(
    data_dir: str,
    service: str,
    environment: str,
    report: dict[str, Any],
) -> str:
    d = onboard_report_dir(data_dir, service, environment)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "latest.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return str(path)


def load_latest_report(data_dir: str, service: str, environment: str) -> dict[str, Any] | None:
    path = onboard_report_dir(data_dir, service, environment) / "latest.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def build_report(
    *,
    service: str,
    environment: str,
    workflow_id: str,
    steps: list[dict[str, Any]],
    payload_set_version: int | None = None,
    tool_count: int | None = None,
    api_count: int | None = None,
    warnings: list[str] | None = None,
    mode: str = "temporal",
) -> dict[str, Any]:
    """Assemble OnboardReport from ordered steps."""
    failed_step: str | None = None
    hard_ok = True
    warns = list(warnings or [])
    for s in steps:
        if not s.get("ok"):
            if s.get("hard_fail"):
                hard_ok = False
                if failed_step is None:
                    failed_step = str(s.get("step") or "")
            else:
                status = str(s.get("status") or "soft_fail")
                err = s.get("error")
                warns.append(f"{s.get('step')}:{status}" + (f" ({err})" if err else ""))
        elif s.get("status") and str(s.get("status")).startswith("warn"):
            warns.append(f"{s.get('step')}:{s.get('status')}")

    return {
        "ok": hard_ok and failed_step is None,
        "failed_step": failed_step,
        "steps": steps,
        "service": service,
        "environment": normalize_env(environment),
        "workflow_id": workflow_id,
        "payload_set_version": payload_set_version,
        "tool_count": tool_count,
        "api_count": api_count,
        "warnings": warns,
        "mode": mode,
    }
