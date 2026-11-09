"""Upsert durable authored flows into local qa-agent for portal Flows rail."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8150"
OUT = Path(__file__).resolve().parent / "AUTHORED_FLOWS_REPORT.json"


def post(url: str, body: dict) -> tuple[int, dict | str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def flow(
    fid: str,
    name: str,
    service: str,
    steps: list[tuple[str, str] | dict],
    **extra,
) -> dict:
    nodes = []
    for i, step in enumerate(steps):
        if isinstance(step, dict):
            node = {
                "id": step.get("id") or f"n{i+1}",
                "kind": "call_tool",
                "service": service,
                "method": str(step.get("method") or "get").lower(),
                "path": step.get("path"),
                "exact_path": step.get("path"),
                "label": step.get("label")
                or f"{str(step.get('method') or 'GET').upper()} {step.get('path')}",
                "auth": bool(step.get("auth", True)),
            }
            for k in (
                "capture",
                "bind_query",
                "bind_path",
                "path_params",
                "body_override",
                "query_override",
                "payload_api_id",
                "optional",
            ):
                if step.get(k) is not None:
                    node[k] = step[k]
            nodes.append(node)
            continue
        method, path = step
        nodes.append(
            {
                "id": f"n{i+1}",
                "kind": "call_tool",
                "service": service,
                "method": method.lower(),
                "path": path,
                "exact_path": path,
                "label": f"{method} {path}",
                "auth": True,
            }
        )
    tags = ["domain-feed", service, extra.get("env", "all")]
    for m in extra.get("modules") or []:
        tags.append(f"module:{m}")
    if extra.get("profile"):
        tags.append(f"profile:{extra['profile']}")
    doc = {
        "id": fid,
        "title": name,
        "name": name,
        "group": service,
        "category": extra.get("category") or "cross_flow",
        "api_pack": service,
        "created_by": "authored",
        "tags": tags,
        "variables": extra.get("variables") or {},
        "payload_set_version": extra.get("payload_set_version"),
        "nodes": nodes,
    }
    return doc


FLOWS = [
    flow(
        "FLOW_MARKET_WATCHLIST_TO_LTP",
        "Watchlist → LTP",
        "am-market-data",
        [
            {
                "method": "GET",
                "path": "/v1/watchlists",
                "capture": {"watchlistId": "$[0].id"},
            },
            {
                "method": "GET",
                "path": "/v1/watchlists/{watchlistId}/items",
                "bind_path": {"watchlistId": "{{watchlistId}}"},
                "capture": {
                    "symbol": "$[0].symbol",
                    "symbols": "$[0].symbol",
                },
            },
            {
                "method": "GET",
                "path": "/v1/market-data/live-ltp",
                "bind_query": {
                    "symbols": "{{symbols}}",
                    "isIndexSymbol": "false",
                },
                "optional": True,
            },
        ],
        env="all",
        modules=["watchlist", "market_data"],
        profile="default",
        category="cross_flow",
        payload_set_version=2,
    ),
    flow(
        "FLOW_MARKET_INDEX_QUOTE_CLUSTER",
        "Index quote cluster",
        "am-market-data",
        [
            {"method": "GET", "path": "/v1/indices/available"},
            {
                "method": "GET",
                "path": "/v1/market-data/live-ltp",
                "bind_query": {
                    "symbols": "{{indexSymbol}}",
                    "isIndexSymbol": "true",
                },
                "optional": True,
            },
            {
                "method": "GET",
                "path": "/v1/market-data/quotes",
                "bind_query": {
                    "symbols": "{{indexSymbol}}",
                    "isIndexSymbol": "true",
                },
            },
        ],
        env="all",
        modules=["market_index", "market_data"],
        profile="default",
        category="cross_flow",
        variables={"indexSymbol": "NIFTY 50"},
        payload_set_version=2,
    ),
    flow(
        "FLOW_MARKET_SEARCH_TO_FUNDAMENTALS",
        "Search → Fundamentals",
        "am-market-data",
        [
            {
                "method": "POST",
                "path": "/v1/instruments/search",
                "capture": {
                    "symbol": [
                        "$[0].symbol",
                        "$[0].asset_symbol",
                        "$[0].trading_symbol",
                        "$[0].name",
                    ]
                },
            },
            {
                "method": "GET",
                "path": "/v1/fundamentals/{symbol}",
                "bind_path": {"symbol": "{{symbol}}"},
            },
        ],
        env="all",
        modules=["instrument", "fundamentals"],
        profile="default",
        category="cross_flow",
        payload_set_version=2,
    ),
    flow(
        "FLOW_MARKET_OPEN_IPO_TO_DETAIL",
        "Open IPO → detail",
        "am-market-data",
        [
            {
                "method": "GET",
                "path": "/v1/market-data/ipo",
                "bind_query": {"status": "open"},
                "capture": {"ipoId": "$[0].id"},
            },
            {"method": "GET", "path": "/v1/market-data/ipo/counts"},
            {
                "method": "GET",
                "path": "/v1/market-data/ipo/{id}",
                "bind_path": {"id": "{{ipoId}}"},
            },
        ],
        env="all",
        modules=["ipo"],
        profile="default",
        category="cross_flow",
        payload_set_version=2,
    ),
    flow(
        "FLOW_MARKET_MF_DETAIL_TO_HISTORY",
        "MF detail → history",
        "am-market-data",
        [
            {
                "method": "GET",
                "path": "/v1/market-data/mutual-fund/{schemeCode}",
                "bind_path": {"schemeCode": "{{schemeCode}}"},
            },
            {
                "method": "GET",
                "path": "/v1/market-data/mutual-fund/{schemeCode}/history",
                "bind_path": {"schemeCode": "{{schemeCode}}"},
            },
        ],
        env="all",
        modules=["mutual_fund"],
        profile="default",
        category="cross_flow",
        variables={"schemeCode": "120503"},
        payload_set_version=2,
    ),
    flow(
        "FLOW_MARKET_WATCHLIST_CREATE_TO_ITEMS",
        "Watchlist create → items (dev-only)",
        "am-market-data",
        [
            {
                "method": "POST",
                "path": "/v1/watchlists",
                "body_override": {"name": "{{watchlistName}}"},
                "capture": {"watchlistId": "$.id"},
            },
            {
                "method": "POST",
                "path": "/v1/watchlists/{watchlistId}/items",
                "bind_path": {"watchlistId": "{{watchlistId}}"},
                "body_override": {
                    "symbol": "{{symbol}}",
                    "exchange": "{{exchange}}",
                },
            },
        ],
        env="dev-only",
        modules=["watchlist"],
        profile="default",
        category="cross_flow",
        variables={
            "watchlistName": "qa-flow-watchlist",
            "symbol": "RELIANCE",
            "exchange": "NSE",
        },
        payload_set_version=2,
    ),
    flow(
        "FLOW_NEWS_HEALTH_TO_AFFAIRS",
        "News health → current affairs",
        "am-news",
        [("GET", "/health"), ("GET", "/v1/current-affairs")],
    ),
    flow(
        "FLOW_NEWS_HOLDINGS",
        "News holdings",
        "am-news",
        [("GET", "/v1/holdings")],
    ),
    flow(
        "FLOW_PARSER_LIST_JOBS",
        "Parser list jobs",
        "am-parser",
        [("GET", "/v1/")],
    ),
    flow(
        "FLOW_PORTFOLIO_LIST_TO_HOLDINGS",
        "Portfolio list → holdings",
        "am-portfolio",
        [("GET", "/v1/portfolios"), ("GET", "/v1/portfolios/holdings")],
    ),
    flow(
        "FLOW_PORTFOLIO_BASKET_CATALOG",
        "Portfolio basket catalog → my",
        "am-portfolio",
        [("GET", "/v1/basket/catalog"), ("GET", "/v1/basket/my")],
    ),
    flow(
        "FLOW_ANALYSIS_ALLOCATION_TO_MOVERS",
        "Analysis allocation → movers",
        "am-analysis",
        [
            ("GET", "/api/v1/analysis/{type}/{id}/allocation"),
            ("GET", "/api/v1/analysis/{type}/{id}/performance"),
            ("GET", "/api/v1/analysis/{type}/{id}/top-movers"),
            ("GET", "/api/v1/analysis/{type}/top-movers"),
        ],
    ),
    flow(
        "FLOW_TRADE_REPLAY_DATE_RANGE",
        "Trade replay date-range",
        "am-trade-management-service",
        [("GET", "/v1/analytics/trade-replays/date-range")],
    ),
    flow(
        "FLOW_OMS_HEALTH_TO_WALLETS",
        "OMS health → wallets",
        "am-oms",
        [("GET", "/health"), ("GET", "/v1/wallets")],
    ),
    flow(
        "FLOW_OMS_WALLET_TO_POSITIONS",
        "OMS wallet → positions → orders",
        "am-oms",
        [
            ("GET", "/v1/wallets"),
            ("GET", "/v1/wallets/{wallet_id}/positions"),
            ("GET", "/v1/orders"),
        ],
    ),
    flow(
        "FLOW_SUBSCRIPTION_PLANS_TO_ME",
        "Subscription plans → me",
        "am-subscription",
        [
            ("GET", "/health"),
            ("GET", "/subscriptions/plans"),
            ("GET", "/subscriptions/me"),
        ],
    ),
    flow(
        "FLOW_XD_MARKET_TO_PORTFOLIO",
        "XD market search → portfolio holdings",
        "am-market-data",
        [
            ("POST", "/v1/instruments/search"),
            ("GET", "/v1/fundamentals/{symbol}"),
        ],
        env="nonprod",
    ),
    # second node service differs — use multi-service nodes
]


def xd_parser_portfolio() -> dict:
    return {
        "id": "FLOW_XD_PARSER_TO_PORTFOLIO",
        "name": "XD parser jobs → portfolio list",
        "group": "cross-domain",
        "created_by": "authored",
        "tags": ["domain-feed", "cross-domain", "dev-only"],
        "nodes": [
            {
                "id": "n1",
                "service": "am-parser",
                "method": "get",
                "path": "/v1/",
                "label": "parser jobs",
            },
            {
                "id": "n2",
                "service": "am-portfolio",
                "method": "get",
                "path": "/v1/portfolios",
                "label": "portfolios",
            },
        ],
    }


def xd_market_portfolio() -> dict:
    return {
        "id": "FLOW_XD_MARKET_TO_PORTFOLIO_HOLDINGS",
        "name": "XD market fundamentals → portfolio holdings",
        "group": "cross-domain",
        "created_by": "authored",
        "tags": ["domain-feed", "cross-domain", "nonprod"],
        "nodes": [
            {
                "id": "n1",
                "service": "am-market-data",
                "method": "post",
                "path": "/v1/instruments/search",
                "label": "search",
            },
            {
                "id": "n2",
                "service": "am-market-data",
                "method": "get",
                "path": "/v1/fundamentals/{symbol}",
                "label": "fundamentals",
            },
            {
                "id": "n3",
                "service": "am-portfolio",
                "method": "get",
                "path": "/v1/portfolios/holdings",
                "label": "holdings",
            },
        ],
    }


def main() -> None:
    docs = list(FLOWS) + [xd_parser_portfolio(), xd_market_portfolio()]
    # drop duplicate stub FLOW_XD_MARKET_TO_PORTFOLIO
    docs = [d for d in docs if d["id"] != "FLOW_XD_MARKET_TO_PORTFOLIO"]
    report = []
    for doc in docs:
        code, out = post(f"{API}/api/flows", doc)
        print(doc["id"], code)
        report.append({"id": doc["id"], "http": code, "out": out if isinstance(out, dict) else str(out)[:300]})
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
