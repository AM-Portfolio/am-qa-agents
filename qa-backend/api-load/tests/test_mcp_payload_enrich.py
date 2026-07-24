"""Unit tests for MCP placeholder enricher."""
from __future__ import annotations

from app.mcp_payload_enrich import enrich_request_from_mcp, is_placeholder


def test_is_placeholder():
    assert is_placeholder(None)
    assert is_placeholder("")
    assert is_placeholder("example")
    assert is_placeholder("pf-demo-001")
    assert is_placeholder("00000000-0000-0000-0000-000000000001")
    assert not is_placeholder("7b43596e-12ef-4ddf-bff6-01c17c2f059a")
    assert not is_placeholder("RELIANCE")
    assert not is_placeholder(0)


def test_enrich_portfolio_id_placeholder():
    req = {
        "method": "GET",
        "path": "/api/v1/portfolios/{portfolioId}",
        "path_params": {"portfolioId": "00000000-0000-0000-0000-000000000001"},
        "query": {},
        "body": None,
    }
    ctx = {"portfolio_id": "7b43596e-12ef-4ddf-bff6-01c17c2f059a", "symbol": "RELIANCE"}
    out = enrich_request_from_mcp(req, ctx)
    assert out["mcp_used"] is True
    assert out["source"] == "mcp"
    assert out["request"]["path_params"]["portfolioId"] == "7b43596e-12ef-4ddf-bff6-01c17c2f059a"
    assert "path.portfolioId" in out["mcp_fields"]
    assert "7b43596e" in out["request"]["resolved_path"]


def test_enrich_preserves_non_placeholder():
    real = "7b43596e-12ef-4ddf-bff6-01c17c2f059a"
    req = {
        "method": "GET",
        "path": "/x",
        "path_params": {},
        "query": {"portfolioId": real},
        "body": None,
    }
    ctx = {"portfolio_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "symbol": "TCS"}
    out = enrich_request_from_mcp(req, ctx)
    assert out["mcp_used"] is False
    assert out["request"]["query"]["portfolioId"] == real


def test_enrich_path_id_when_type_portfolio():
    req = {
        "method": "GET",
        "path": "/api/v1/{type}/{id}/performance",
        "path_params": {"type": "PORTFOLIO", "id": "pf-demo-001"},
        "query": {"timeFrame": "1D"},
        "body": None,
    }
    ctx = {"portfolio_id": "e759ea76-b16f-44f9-9e0c-3c0a6c6b096a"}
    out = enrich_request_from_mcp(req, ctx)
    assert out["mcp_used"] is True
    assert out["request"]["path_params"]["id"] == "e759ea76-b16f-44f9-9e0c-3c0a6c6b096a"
    assert out["request"]["path_params"]["type"] == "PORTFOLIO"


def test_enrich_skips_id_when_type_not_portfolio():
    req = {
        "method": "GET",
        "path": "/api/v1/{type}/{id}/performance",
        "path_params": {"type": "BASKET", "id": "pf-demo-001"},
        "query": {},
        "body": None,
    }
    ctx = {"portfolio_id": "e759ea76-b16f-44f9-9e0c-3c0a6c6b096a"}
    out = enrich_request_from_mcp(req, ctx)
    assert out["mcp_used"] is False
    assert out["request"]["path_params"]["id"] == "pf-demo-001"


def test_enrich_symbol():
    req = {
        "method": "GET",
        "path": "/quote",
        "path_params": {},
        "query": {"symbol": "example"},
        "body": None,
    }
    out = enrich_request_from_mcp(req, {"symbol": "INFY"})
    assert out["request"]["query"]["symbol"] == "INFY"


def test_pick_portfolio_filters_unknown():
    from app.mcp_data_client import _pick_portfolio

    picked = _pick_portfolio(
        [
            {"portfolioId": "bad", "portfolioName": "UNKNOWN", "holdingCount": 99},
            {"portfolioId": "good", "portfolioName": "zerodha", "holdingCount": 2},
        ]
    )
    assert picked is not None
    assert picked["portfolioId"] == "good"
