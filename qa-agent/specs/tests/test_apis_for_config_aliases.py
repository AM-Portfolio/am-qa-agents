"""selected_api_ids may be catalog id or OpenAPI operation_id."""

from __future__ import annotations

import pytest

from specs.catalog import catalog_loader as cl


@pytest.fixture()
def stub_catalog(monkeypatch: pytest.MonkeyPatch):
    catalog = {
        "base_url": "{{target_url}}",
        "apis": [
            {
                "id": "get.v1.market.data.ipo",
                "operation_id": "get_v1_market-data_ipo",
                "method": "GET",
                "path": "/v1/market-data/ipo",
                "headers": {},
                "query": {},
            },
            {
                "id": "get.v1.indices.available",
                "operation_id": "get_v1_indices_available",
                "method": "GET",
                "path": "/v1/indices/available",
                "headers": {},
                "query": {},
            },
        ],
    }
    monkeypatch.setattr(cl, "load_service_apis", lambda *_a, **_k: catalog)
    monkeypatch.setattr(
        cl,
        "reachable_target_for_service",
        lambda *_a, **_k: "https://am-dev.asrax.in/market",
    )
    return catalog


def test_apis_for_config_matches_dotted_catalog_id(stub_catalog):
    base, apis = cl.apis_for_config(
        {
            "service": "am-market-data",
            "environment": "dev",
            "selected_api_ids": ["get.v1.market.data.ipo"],
        },
        run_id="t1",
    )
    assert base
    assert [a["id"] for a in apis] == ["get.v1.market.data.ipo"]


def test_apis_for_config_matches_operation_id_alias(stub_catalog):
    _, apis = cl.apis_for_config(
        {
            "service": "am-market-data",
            "environment": "dev",
            "selected_api_ids": ["get_v1_market-data_ipo", "get_v1_indices_available"],
        },
        run_id="t2",
    )
    assert {a["id"] for a in apis} == {
        "get.v1.market.data.ipo",
        "get.v1.indices.available",
    }


def test_apis_for_config_drops_unknown_when_some_match(stub_catalog):
    _, apis = cl.apis_for_config(
        {
            "service": "am-market-data",
            "environment": "dev",
            "selected_api_ids": ["get_v1_market-data_ipo", "no_such_api"],
        },
        run_id="t3",
    )
    assert [a["id"] for a in apis] == ["get.v1.market.data.ipo"]


def test_apis_for_config_all_unknown_still_raises(stub_catalog):
    with pytest.raises(ValueError, match="Unknown api_id"):
        cl.apis_for_config(
            {
                "service": "am-market-data",
                "environment": "dev",
                "selected_api_ids": ["no_such_api", "also_missing"],
            },
            run_id="t4",
        )
