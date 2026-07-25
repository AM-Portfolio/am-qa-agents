"""Fill placeholder request fields from MCP prep context (generic param names only)."""
from __future__ import annotations

import copy
import re
from typing import Any

_NIL_UUID = re.compile(
    r"^0{8}-0{4}-0{4}-0{4}-0{12}$",
    re.IGNORECASE,
)
_DEMO_IDS = frozenset(
    {
        "example",
        "pf-demo-001",
        "portfolio-demo",
        "string",
        "null",
        "none",
        "n/a",
        "na",
        "todo",
        "changeme",
    }
)

_PORTFOLIO_KEYS = frozenset({"portfolioid", "portfolio_id"})
_SYMBOL_KEYS = frozenset({"symbol", "ticker", "tradingsymbol", "trading_symbol"})


def is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return False
    text = str(value).strip()
    if not text:
        return True
    low = text.lower()
    if low in _DEMO_IDS:
        return True
    if _NIL_UUID.match(text):
        return True
    if text.startswith("00000000-"):
        return True
    return False


def _norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", key.strip().lower())


def _resolve_path(path: str, path_params: dict[str, Any]) -> str:
    resolved = path
    for k, v in path_params.items():
        resolved = resolved.replace("{" + str(k) + "}", str(v))
    return resolved


def _fill_mapping(
    mapping: dict[str, Any] | None,
    ctx: dict[str, Any],
    *,
    sibling: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Return (new_mapping, list of filled field names)."""
    if not isinstance(mapping, dict):
        return {}, []
    out = dict(mapping)
    filled: list[str] = []
    sib = sibling or {}
    merged_for_type = {**sib, **out}

    for key, val in list(out.items()):
        if not is_placeholder(val):
            continue
        nk = _norm_key(key)
        new_val: Any = None

        if nk in _PORTFOLIO_KEYS or nk == "portfolioid":
            new_val = ctx.get("portfolio_id")
        elif nk in _SYMBOL_KEYS:
            new_val = ctx.get("symbol")
        elif nk in ("userid", "user_id"):
            new_val = ctx.get("user_id")
        elif nk == "id":
            # Entity path {type}/{id}: only when type is PORTFOLIO
            type_val = str(
                merged_for_type.get("type")
                or merged_for_type.get("entityType")
                or ""
            ).upper()
            if type_val == "PORTFOLIO" and ctx.get("portfolio_id"):
                new_val = ctx["portfolio_id"]

        if new_val is not None and str(new_val).strip():
            out[key] = new_val
            filled.append(key)

    return out, filled


def enrich_request_from_mcp(
    request: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """
    Replace placeholder path/query/body fields using MCP context.
    Never overwrites non-placeholder values (preserves overlay/set).
    """
    if not ctx or not isinstance(request, dict):
        return {
            "request": request,
            "mcp_used": False,
            "mcp_fields": [],
            "source": None,
        }

    req = copy.deepcopy(request)
    all_filled: list[str] = []

    path_params = req.get("path_params") if isinstance(req.get("path_params"), dict) else {}
    query = req.get("query") if isinstance(req.get("query"), dict) else {}
    body = req.get("body")

    new_pp, f1 = _fill_mapping(path_params, ctx, sibling={**query, **(body if isinstance(body, dict) else {})})
    new_q, f2 = _fill_mapping(query, ctx, sibling={**new_pp, **(body if isinstance(body, dict) else {})})
    f3: list[str] = []
    new_body = body
    if isinstance(body, dict):
        new_body, f3 = _fill_mapping(body, ctx, sibling={**new_pp, **new_q})

    if f1:
        req["path_params"] = new_pp
        all_filled.extend(f"path.{k}" for k in f1)
    if f2:
        req["query"] = new_q
        all_filled.extend(f"query.{k}" for k in f2)
    if f3:
        req["body"] = new_body
        all_filled.extend(f"body.{k}" for k in f3)

    if all_filled and req.get("path") and req.get("path_params"):
        req["resolved_path"] = _resolve_path(str(req["path"]), req["path_params"])

    return {
        "request": req,
        "mcp_used": bool(all_filled),
        "mcp_fields": all_filled,
        "source": "mcp" if all_filled else None,
    }


def request_needs_portfolio_mapping(request: dict[str, Any] | None) -> bool:
    """True when request has a portfolio-related placeholder that MCP can fill."""
    if not isinstance(request, dict):
        return False
    path_params = request.get("path_params") if isinstance(request.get("path_params"), dict) else {}
    query = request.get("query") if isinstance(request.get("query"), dict) else {}
    body = request.get("body") if isinstance(request.get("body"), dict) else {}
    merged = {**path_params, **query, **body}
    for key, val in merged.items():
        if not is_placeholder(val):
            continue
        nk = _norm_key(str(key))
        if nk in _PORTFOLIO_KEYS or nk in _SYMBOL_KEYS or nk in ("userid", "user_id"):
            return True
        if nk == "id":
            type_val = str(merged.get("type") or merged.get("entityType") or "").upper()
            if type_val == "PORTFOLIO":
                return True
    return False

