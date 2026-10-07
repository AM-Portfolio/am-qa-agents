"""Hand-seeded data_generator helpers (SPT login + plans/me). Inject call_tool for tests."""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

CallToolFn = Callable[..., dict[str, Any]]


def _norm_env(env: str) -> str:
    e = (env or "dev").strip().lower()
    return "dev" if e == "dig" else e


def _find_tool(
    tools: list[dict[str, Any]],
    *,
    path_contains: str = "",
    tool_match: list[str] | None = None,
    method: str = "",
) -> dict[str, Any] | None:
    method_l = (method or "").lower()
    matches = tool_match or []
    for t in tools:
        path = str(t.get("path") or t.get("operation_path") or "").lower()
        name = str(t.get("name") or "").lower()
        m = str(t.get("method") or "").lower()
        if method_l and m and m != method_l:
            continue
        if path_contains and path_contains.lower() not in path:
            continue
        if matches and not any(x.lower() in path or x.lower() in name for x in matches):
            continue
        if path_contains or matches:
            return t
    return None


def prepare_subscription(
    *,
    env: str,
    ctx: dict[str, Any] | None = None,
    assert_only: bool = False,
    refresh: bool = True,
    call_tool: Optional[CallToolFn] = None,
    list_tools_fn: Optional[Callable[..., dict[str, Any]]] = None,
    refresh_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Ordered prep: login -> plans + me.
    assert_only (Contabo prod): never grant/ensure; soft-fail optional reads.
    fail-closed for dev when login missing/fails.
    """
    env_n = _norm_env(env)
    steps: list[dict[str, Any]] = []
    user = os.environ.get("SPT_AUTH_USERNAME") or ""
    password = os.environ.get("SPT_AUTH_PASSWORD") or ""

    if call_tool is None or list_tools_fn is None:
        try:
            from specs.openapi_tools.registry import (
                call_tool as _ct,
                list_tools as _lt,
                refresh_tools_from_prod as _rf,
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "env": env_n,
                "assert_only": assert_only,
                "error": f"openapi_tools unavailable: {exc}",
                "steps": steps,
            }
        call_tool = call_tool or _ct
        list_tools_fn = list_tools_fn or _lt
        refresh_fn = refresh_fn or _rf

    refresh_info: dict[str, Any] = {}
    if refresh and refresh_fn is not None:
        try:
            refresh_info = refresh_fn(
                environment=env_n, services=["am-identity", "am-subscription"]
            )
        except Exception as exc:  # noqa: BLE001
            refresh_info = {"error": str(exc)}

    id_tools = list(
        (list_tools_fn(service="am-identity", limit=1000) or {}).get("tools") or []
    )
    sub_tools = list(
        (list_tools_fn(service="am-subscription", limit=1000) or {}).get("tools") or []
    )

    login_tool = _find_tool(
        id_tools, path_contains="/auth/login", method="post")
    if login_tool is None:
        login_tool = _find_tool(id_tools, tool_match=["login"], method="post")

    access_token: str | None = None
    if not user or not password:
        steps.append(
            {
                "id": "login",
                "status": "FAILED",
                "reason": "SPT_AUTH_USERNAME/PASSWORD not set",
            }
        )
        if not assert_only:
            return {
                "ok": False,
                "env": env_n,
                "assert_only": assert_only,
                "fail_closed": env_n == "dev",
                "refresh": refresh_info,
                "steps": steps,
            }
    elif login_tool is None:
        steps.append(
            {"id": "login", "status": "FAILED", "reason": "login tool not found"}
        )
        if not assert_only:
            return {
                "ok": False,
                "env": env_n,
                "assert_only": assert_only,
                "fail_closed": env_n == "dev",
                "refresh": refresh_info,
                "steps": steps,
            }
    else:
        out = call_tool(
            str(login_tool["name"]),
            {"username": user, "password": password, "email": user},
            with_identity_auth=False,
            record_run=False,
        )
        ok = bool(out.get("ok"))
        body = out.get("body") if isinstance(out.get("body"), dict) else {}
        if ok and body:
            access_token = (
                body.get("access_token")
                or body.get("accessToken")
                or (body.get("data") or {}).get("access_token")
            )
        steps.append(
            {
                "id": "login",
                "status": "PASSED" if ok and access_token else "FAILED",
                "tool": login_tool.get("name"),
                "http_status": out.get("status"),
                "has_token": bool(access_token),
            }
        )
        if not (ok and access_token) and not assert_only:
            return {
                "ok": False,
                "env": env_n,
                "assert_only": assert_only,
                "fail_closed": env_n == "dev",
                "refresh": refresh_info,
                "steps": steps,
            }

    if assert_only:
        steps.append(
            {
                "id": "ensure_grant",
                "status": "SKIPPED",
                "reason": "assert_only (Contabo prod)",
            }
        )
    else:
        ensure = _find_tool(
            sub_tools, tool_match=["ensure", "grant", "trial"], method="post"
        )
        if ensure:
            steps.append(
                {
                    "id": "ensure_grant",
                    "status": "SKIPPED",
                    "reason": "tool present but not auto-called in v1",
                    "tool": ensure.get("name"),
                }
            )
        else:
            steps.append(
                {
                    "id": "ensure_grant",
                    "status": "SKIPPED",
                    "reason": "no ensure/grant tool in registry",
                }
            )

    for sid, match, path_bit in (
        ("sub_plans", ["plan"], "/plan"),
        ("sub_me", ["subscription", "me", "current"], "/me"),
    ):
        tool = _find_tool(sub_tools, tool_match=match, method="get")
        if tool is None:
            tool = _find_tool(sub_tools, path_contains=path_bit, method="get")
        if tool is None:
            steps.append(
                {
                    "id": sid,
                    "status": "SOFT_FAIL" if assert_only else "FAILED",
                    "reason": "tool not found",
                }
            )
            if not assert_only and sid == "sub_me":
                return {
                    "ok": False,
                    "env": env_n,
                    "assert_only": assert_only,
                    "fail_closed": env_n == "dev",
                    "refresh": refresh_info,
                    "steps": steps,
                }
            continue
        out = call_tool(
            str(tool["name"]),
            {},
            with_identity_auth=bool(access_token),
            record_run=False,
        )
        ok = bool(out.get("ok")) or (out.get("status") in (200, 201))
        steps.append(
            {
                "id": sid,
                "status": "PASSED" if ok else ("SOFT_FAIL" if assert_only else "FAILED"),
                "tool": tool.get("name"),
                "http_status": out.get("status"),
            }
        )
        if not ok and not assert_only and sid == "sub_me":
            return {
                "ok": False,
                "env": env_n,
                "assert_only": assert_only,
                "fail_closed": env_n == "dev",
                "refresh": refresh_info,
                "steps": steps,
            }

    failed = [s for s in steps if s.get("status") == "FAILED"]
    return {
        "ok": len(failed) == 0,
        "env": env_n,
        "assert_only": assert_only,
        "fail_closed": env_n == "dev" and len(failed) > 0,
        "refresh": refresh_info,
        "steps": steps,
        "ctx_keys": sorted((ctx or {}).keys()),
    }


def prepare_identity(
    *,
    env: str,
    ctx: dict[str, Any] | None = None,
    assert_only: bool = False,
    refresh: bool = True,
    call_tool: Optional[CallToolFn] = None,
    list_tools_fn: Optional[Callable[..., dict[str, Any]]] = None,
    refresh_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Identity prep: login JWT only (fail-closed on dev)."""
    env_n = _norm_env(env)
    steps: list[dict[str, Any]] = []
    user = os.environ.get("SPT_AUTH_USERNAME") or ""
    password = os.environ.get("SPT_AUTH_PASSWORD") or ""

    if call_tool is None or list_tools_fn is None:
        try:
            from specs.openapi_tools.registry import (
                call_tool as _ct,
                list_tools as _lt,
                refresh_tools_from_prod as _rf,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "env": env_n, "error": str(exc), "steps": steps}
        call_tool = call_tool or _ct
        list_tools_fn = list_tools_fn or _lt
        refresh_fn = refresh_fn or _rf

    if refresh and refresh_fn is not None:
        try:
            refresh_fn(environment=env_n, services=["am-identity"])
        except Exception:  # noqa: BLE001
            pass

    tools = list(
        (list_tools_fn(service="am-identity", limit=1000) or {}).get("tools") or []
    )
    login_tool = _find_tool(tools, path_contains="/auth/login", method="post")
    if login_tool is None:
        login_tool = _find_tool(tools, tool_match=["login"], method="post")

    if not user or not password or login_tool is None:
        steps.append(
            {
                "id": "login",
                "status": "FAILED",
                "reason": (
                    "SPT_AUTH missing"
                    if not user or not password
                    else "login tool not found"
                ),
            }
        )
        if assert_only:
            steps[-1]["status"] = "SOFT_FAIL"
            return {
                "ok": True,
                "env": env_n,
                "assert_only": True,
                "steps": steps,
                "ctx_keys": sorted((ctx or {}).keys()),
            }
        return {
            "ok": False,
            "env": env_n,
            "assert_only": False,
            "fail_closed": env_n == "dev",
            "steps": steps,
        }

    out = call_tool(
        str(login_tool["name"]),
        {"username": user, "password": password, "email": user},
        with_identity_auth=False,
        record_run=False,
    )
    body = out.get("body") if isinstance(out.get("body"), dict) else {}
    token = None
    if body:
        token = (
            body.get("access_token")
            or body.get("accessToken")
            or (body.get("data") or {}).get("access_token")
        )
    ok = bool(out.get("ok")) and bool(token)
    steps.append(
        {
            "id": "login",
            "status": "PASSED" if ok else ("SOFT_FAIL" if assert_only else "FAILED"),
            "tool": login_tool.get("name"),
            "has_token": bool(token),
        }
    )
    return {
        "ok": ok or assert_only,
        "env": env_n,
        "assert_only": assert_only,
        "fail_closed": env_n == "dev" and not ok and not assert_only,
        "steps": steps,
        "ctx_keys": sorted((ctx or {}).keys()),
    }
