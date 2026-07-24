"""Fetch real portfolio/market facts from am-mcp-server for payload prep."""
from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.mcp_sse_client import call_mcp_tool

logger = logging.getLogger(__name__)

_CACHE: dict[str, Any] = {"at": 0.0, "ctx": None}
_CACHE_TTL_SEC = 60.0


def _parse_portfolios(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if isinstance(raw, dict):
        items = raw.get("portfolios") or raw.get("data") or []
        if isinstance(items, list):
            return [p for p in items if isinstance(p, dict)]
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]
    return []


def _parse_holdings(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if isinstance(raw, dict):
        items = raw.get("holdings") or raw.get("data") or raw.get("items") or []
        if isinstance(items, list):
            return [h for h in items if isinstance(h, dict)]
        # single holding envelope
        if raw.get("symbol"):
            return [raw]
    if isinstance(raw, list):
        return [h for h in raw if isinstance(h, dict)]
    return []


def _pick_portfolio(portfolios: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer named non-UNKNOWN portfolios with holdings when count is present."""
    scored: list[tuple[int, dict[str, Any]]] = []
    for p in portfolios:
        name = str(p.get("portfolioName") or p.get("name") or "").strip()
        if not name or name.upper() == "UNKNOWN":
            continue
        pid = p.get("portfolioId") or p.get("id")
        if not pid:
            continue
        hc = p.get("holdingCount")
        try:
            count = int(hc) if hc is not None else -1
        except (TypeError, ValueError):
            count = -1
        # higher score = better; unknown count still ok (score 1)
        score = 10 + max(count, 0) if count >= 0 else 5
        scored.append((score, p))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _pick_symbol(holdings: list[dict[str, Any]]) -> str | None:
    for h in holdings:
        sym = str(h.get("symbol") or h.get("ticker") or "").strip()
        if not sym or sym.lower() == "example":
            continue
        qty = h.get("quantity")
        if qty is not None:
            try:
                if float(qty) <= 0:
                    continue
            except (TypeError, ValueError):
                pass
        return sym.upper()
    return None


def _empty_context() -> dict[str, Any]:
    return {
        "portfolio_id": None,
        "portfolio_ids": [],
        "symbol": None,
        "symbols": [],
        "user_id": (settings.spt_mcp_user_id or settings.spt_user_id or "").strip() or None,
    }


def fetch_prep_context(*, force: bool = False) -> dict[str, Any]:
    """Best-effort MCP facts. Returns empty-ish context on any failure."""
    now = time.time()
    if (
        not force
        and _CACHE.get("ctx") is not None
        and (now - float(_CACHE.get("at") or 0)) < _CACHE_TTL_SEC
    ):
        return dict(_CACHE["ctx"])

    ctx = _empty_context()
    base = (settings.spt_mcp_server_url or "").strip()
    if not base:
        logger.debug("MCP enrich skipped: spt_mcp_server_url unset")
        _CACHE["ctx"] = ctx
        _CACHE["at"] = now
        return ctx

    token: str | None = None
    try:
        from app.catalog_loader import platform_bearer_token

        token = platform_bearer_token()
    except Exception as exc:
        logger.warning("MCP enrich: identity token unavailable: %s", exc)

    timeout = float(settings.spt_mcp_timeout_seconds or 30)

    def _call(tool: str, args: dict[str, Any] | None = None) -> Any:
        return call_mcp_tool(
            base,
            tool,
            args or {},
            bearer_token=token,
            timeout_seconds=timeout,
        )

    try:
        overviews = _call("get_portfolio_overviews", {})
        portfolios = _parse_portfolios(overviews)
        ids: list[str] = []
        for p in portfolios:
            pid = p.get("portfolioId") or p.get("id")
            name = str(p.get("portfolioName") or p.get("name") or "")
            if pid and name.upper() != "UNKNOWN":
                ids.append(str(pid))
        ctx["portfolio_ids"] = ids
        picked = _pick_portfolio(portfolios)
        if picked:
            ctx["portfolio_id"] = str(picked.get("portfolioId") or picked.get("id"))
    except Exception as exc:
        logger.warning("MCP get_portfolio_overviews failed: %s", exc)

    try:
        holdings_raw = _call("get_holdings", {})
        holdings = _parse_holdings(holdings_raw)
        symbols: list[str] = []
        for h in holdings:
            sym = str(h.get("symbol") or h.get("ticker") or "").strip().upper()
            if sym and sym not in symbols:
                symbols.append(sym)
        ctx["symbols"] = symbols
        ctx["symbol"] = _pick_symbol(holdings) or (symbols[0] if symbols else None)
    except Exception as exc:
        logger.warning("MCP get_holdings failed: %s", exc)

    if not ctx.get("symbol"):
        try:
            search = _call("search_instruments", {"query": "RELIANCE"})
            if isinstance(search, dict):
                items = search.get("instruments") or search.get("data") or search.get("results") or []
                if isinstance(items, list) and items and isinstance(items[0], dict):
                    sym = items[0].get("symbol") or items[0].get("ticker")
                    if sym:
                        ctx["symbol"] = str(sym).upper()
                        ctx["symbols"] = [ctx["symbol"]]
            elif isinstance(search, list) and search and isinstance(search[0], dict):
                sym = search[0].get("symbol") or search[0].get("ticker")
                if sym:
                    ctx["symbol"] = str(sym).upper()
                    ctx["symbols"] = [ctx["symbol"]]
        except Exception as exc:
            logger.debug("MCP search_instruments skipped: %s", exc)

    _CACHE["ctx"] = ctx
    _CACHE["at"] = now
    return dict(ctx)


def clear_prep_context_cache() -> None:
    _CACHE["ctx"] = None
    _CACHE["at"] = 0.0
