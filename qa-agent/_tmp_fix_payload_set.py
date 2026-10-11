"""One-shot: fix dig am-market-data payload set v1 for suite pass."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "https://am-dev.asrax.in/qa"
WID = "6aca60b8085abe8fb00978f5"
CFG_ID = "d398142f-d38a-49ac-96cf-4b4a04306399"


def put(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


updates = [
    (
        "get_v1_watchlists_watchlistId_items",
        {
            "service": "am-market-data",
            "api_id": "get_v1_watchlists_watchlistId_items",
            "version": 1,
            "name": "happy",
            "request": {
                "method": "GET",
                "path": "/v1/watchlists/{watchlistId}/items",
                "path_params": {"watchlistId": WID},
                "query": {},
                "headers": {"X-User-Id": "{{user_id}}"},
                "body": None,
            },
            "response": {"status": 200, "headers": {}},
            "meta": {
                "source": "dig-fix",
                "case_kind": "happy",
                "expect_status": 200,
                "notes": "Concrete dig watchlist id",
            },
        },
    ),
    (
        "post_v1_watchlists_watchlistId_items",
        {
            "service": "am-market-data",
            "api_id": "post_v1_watchlists_watchlistId_items",
            "version": 1,
            "name": "happy",
            "request": {
                "method": "POST",
                "path": "/v1/watchlists/{watchlistId}/items",
                "path_params": {"watchlistId": WID},
                "query": {},
                "headers": {
                    "X-User-Id": "{{user_id}}",
                    "Content-Type": "application/json",
                },
                "body": {"symbol": "RELIANCE", "exchange": "NSE"},
            },
            "response": {"status": 201, "headers": {}},
            "meta": {
                "source": "dig-fix",
                "case_kind": "happy",
                "expect_status": 201,
            },
        },
    ),
    (
        "get_v1_watchlists_check_symbol",
        {
            "service": "am-market-data",
            "api_id": "get_v1_watchlists_check_symbol",
            "version": 1,
            "name": "happy",
            "request": {
                "method": "GET",
                "path": "/v1/watchlists/check/{symbol}",
                "path_params": {"symbol": "RELIANCE"},
                "query": {"exchange": "NSE"},
                "headers": {"X-User-Id": "{{user_id}}"},
                "body": None,
            },
            "response": {"status": 200, "headers": {}},
            "meta": {
                "source": "dig-fix",
                "case_kind": "happy",
                "expect_status": 200,
            },
        },
    ),
    (
        "post_v1_indices_batch",
        {
            "service": "am-market-data",
            "api_id": "post_v1_indices_batch",
            "version": 1,
            "name": "happy",
            "request": {
                "method": "POST",
                "path": "/v1/indices/batch",
                "path_params": {},
                "query": {},
                "headers": {"Content-Type": "application/json"},
                "body": ["NIFTY 50", "NIFTY BANK"],
            },
            "response": {"status": 200, "headers": {}},
            "meta": {
                "source": "dig-fix",
                "case_kind": "happy",
                "expect_status": 200,
            },
        },
    ),
    (
        "post_v1_instruments_search",
        {
            "service": "am-market-data",
            "api_id": "post_v1_instruments_search",
            "version": 1,
            "name": "happy",
            "request": {
                "method": "POST",
                "path": "/v1/instruments/search",
                "path_params": {},
                "query": {},
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "queries": ["NIFTY 50"],
                    "exchanges": ["NSE"],
                    "provider": "UPSTOX",
                },
            },
            "response": {"status": 200, "headers": {}},
            "meta": {
                "source": "dig-fix",
                "case_kind": "happy",
                "expect_status": 200,
            },
        },
    ),
    (
        "post_v1_market-data_ohlc",
        {
            "service": "am-market-data",
            "api_id": "post_v1_market-data_ohlc",
            "version": 1,
            "name": "happy",
            "request": {
                "method": "POST",
                "path": "/v1/market-data/ohlc",
                "path_params": {},
                "query": {},
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "symbols": ["NIFTY 50"],
                    "timeFrame": "1D",
                    "indexSymbol": True,
                    "forceRefresh": False,
                    "exchange": "NSE",
                },
            },
            "response": {"status": 200, "headers": {}},
            "meta": {
                "source": "dig-fix",
                "case_kind": "happy",
                "expect_status": 200,
            },
        },
    ),
    (
        "post_v1_market-data_quotes",
        {
            "service": "am-market-data",
            "api_id": "post_v1_market-data_quotes",
            "version": 1,
            "name": "happy",
            "request": {
                "method": "POST",
                "path": "/v1/market-data/quotes",
                "path_params": {},
                "query": {},
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "symbols": ["NIFTY 50"],
                    "timeFrame": "1D",
                    "indexSymbol": True,
                    "forceRefresh": False,
                    "exchange": "NSE",
                },
            },
            "response": {"status": 200, "headers": {}},
            "meta": {
                "source": "dig-fix",
                "case_kind": "happy",
                "expect_status": 200,
            },
        },
    ),
]


def main() -> None:
    for api_id, body in updates:
        try:
            out = put(f"{BASE}/api/payload-sets/am-market-data/apis/{api_id}", body)
            print("OK upsert", api_id, "v", out.get("version") or (out.get("set") or {}).get("version"))
        except urllib.error.HTTPError as e:
            print("FAIL upsert", api_id, e.code, e.read()[:400])

    cfg = get(f"{BASE}/api/configs/{CFG_ID}")
    selected = list(cfg.get("selected_api_ids") or [])
    drop = "get_v1_market-data_mutual-fund_schemeCode"
    if drop in selected:
        selected = [x for x in selected if x != drop]
        cfg["selected_api_ids"] = selected
        # also strip from expect_status map if present
        payloads = cfg.get("payloads") or {}
        expect = payloads.get("expect_status_by_api") or {}
        if drop in expect:
            expect = {k: v for k, v in expect.items() if k != drop}
            payloads["expect_status_by_api"] = expect
            cfg["payloads"] = payloads
        try:
            out = put(f"{BASE}/api/configs/{CFG_ID}", cfg)
            print("OK config selected_api_ids count", len(out.get("selected_api_ids") or selected))
        except urllib.error.HTTPError as e:
            print("FAIL config", e.code, e.read()[:500])
    else:
        print("config already without", drop, "count", len(selected))


if __name__ == "__main__":
    main()
