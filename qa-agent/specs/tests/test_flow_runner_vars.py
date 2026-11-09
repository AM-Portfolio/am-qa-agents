"""Unit tests for flow var interpolate, body_override, and bind synthesis."""
from __future__ import annotations

from specs.data_gen.workflows import _steps_from_examples, _template_bind_map
from specs.flows.runner import (
    _apply_bindings,
    _interpolate,
    _merge_body_override,
)


def test_interpolate_nested_list_and_dict():
    vars_ = {"symbol": "RELIANCE", "exchange": "NSE"}
    body = {"queries": ["{{symbol}}"], "exchanges": ["{{exchange}}"], "nested": {"s": "{{symbol}}"}}
    out = _interpolate(body, vars_)
    assert out == {
        "queries": ["RELIANCE"],
        "exchanges": ["NSE"],
        "nested": {"s": "RELIANCE"},
    }


def test_merge_body_override_resolves_templates():
    args = {"provider": "UPSTOX"}
    override = {"queries": ["{{symbol}}"], "exchanges": ["{{exchange}}"]}
    merged = _merge_body_override(args, override, {"symbol": "RELIANCE", "exchange": "NSE"})
    assert "{{" not in str(merged)
    assert merged["queries"] == ["RELIANCE"]
    assert merged["exchanges"] == ["NSE"]
    assert merged["provider"] == "UPSTOX"


def test_apply_bindings_path_params_with_capture_vars():
    node = {
        "path_params": {"watchlistId": "{{watchlistId}}"},
        "bind_path": {"watchlistId": "{{watchlistId}}"},
    }
    args = _apply_bindings(node, {}, {"watchlistId": "wl-1"})
    assert args.get("watchlistId") == "wl-1"


def test_template_bind_map_and_steps_synthesize_bind_path():
    assert _template_bind_map({"id": "{{ipoId}}", "plain": "x"}) == {"id": "{{ipoId}}"}
    examples = [
        {
            "name": "ipo-detail",
            "request": {
                "method": "GET",
                "path": "/v1/market-data/ipo/{id}",
                "path_params": {"id": "{{ipoId}}"},
                "query": {},
            },
            "meta": {
                "case_kind": "cross_flow",
                "flow_id": "open_ipo_to_detail",
                "flow_step": 2,
                "variant_id": "ipo-detail",
                "capture": None,
            },
            "response": {"status": 200},
        }
    ]
    nodes = _steps_from_examples(examples, service="am-market-data")
    assert len(nodes) == 1
    assert nodes[0].get("bind_path") == {"id": "{{ipoId}}"}


def test_steps_substitute_body_with_variables():
    examples = [
        {
            "name": "search",
            "request": {
                "method": "POST",
                "path": "/v1/instruments/search",
                "body": {
                    "queries": ["{{symbol}}"],
                    "exchanges": ["{{exchange}}"],
                    "symbols": ["{{symbol}}"],  # must be stripped — live Jackson rejects
                },
            },
            "meta": {
                "case_kind": "cross_flow",
                "flow_id": "search_to_fundamentals",
                "flow_step": 0,
                "variant_id": "search-s0",
            },
            "response": {"status": 200},
        }
    ]
    nodes = _steps_from_examples(
        examples,
        service="am-market-data",
        variables={"symbol": "RELIANCE", "exchange": "NSE"},
    )
    assert nodes[0]["body_override"]["queries"] == ["RELIANCE"]
    assert "symbols" not in nodes[0]["body_override"]
    assert nodes[0]["capture"]["symbol"] == "$[0].trading_symbol"
    assert "{{" not in str(nodes[0]["body_override"])
