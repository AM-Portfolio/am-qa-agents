"""Path params must be substituted before k6 hits the target (not literal {id})."""
from __future__ import annotations

from specs.catalog.catalog_loader import resolve_api
from specs.load.script_generator import generate_k6_script


def test_resolve_api_applies_path_params():
    out = resolve_api(
        {
            "id": "get_v1_market-data_ipo_id",
            "method": "GET",
            "path": "/v1/market-data/ipo/{id}",
            "path_params": {"id": "hd-fire-protect-limited-ipo"},
            "headers": {},
            "query": {},
        },
        {},
        {},
    )
    assert out["path"] == "/v1/market-data/ipo/hd-fire-protect-limited-ipo"
    assert "{" not in out["path"]
    assert out["path_params"]["id"] == "hd-fire-protect-limited-ipo"


def test_resolve_api_keeps_json_body_and_sets_content_type():
    out = resolve_api(
        {
            "id": "post_v1_indices_batch",
            "method": "POST",
            "path": "/v1/indices/batch",
            "path_params": {},
            "headers": {},
            "query": {},
            "body": ["NIFTY 50", "{{index}}"],
        },
        {"index": "NIFTY BANK"},
        {},
    )
    assert out["body"] == ["NIFTY 50", "NIFTY BANK"]
    assert isinstance(out["body"], list)
    assert out["headers"].get("Content-Type") == "application/json"


def test_k6_build_url_substitutes_path_params():
    script = generate_k6_script(
        [
            {
                "id": "get_ipo",
                "name": "get_ipo",
                "method": "GET",
                "path": "/v1/market-data/ipo/{id}",
                "path_params": {"id": "hd-fire-protect-limited-ipo"},
                "query": {},
                "headers": {},
                "body": None,
                "checks": ["status_2xx"],
            }
        ],
        service="am-market-data",
        vus=1,
        duration="1s",
        iterations=1,
    )
    assert "path_params" in script
    assert "split('{' + k + '}')" in script
    assert "let url = BASE_URL + api.path;" not in script.split("function doRequest")[0]
    assert "JSON.stringify(body)" in script
    assert "headers['Content-Type'] = 'application/json'" in script
