"""Payload-set / Postman overrides must match OpenAPI ops by method+path."""

from specs.catalog.catalog_loader import merge_api_overrides


def test_merge_overrides_by_method_path_keeps_catalog_id_and_count():
    catalog = [
        {
            "id": "health.health.get",
            "method": "GET",
            "path": "/health",
            "headers": {"Accept": "application/json"},
            "query": {},
        },
        {
            "id": "upgrade.subscription.subscriptions.subscription.id.upgrade.patch",
            "method": "PATCH",
            "path": "/subscriptions/{subscription_id}/upgrade",
            "headers": {},
            "query": {},
            "body": None,
        },
    ]
    # Postman-style ids (do not match OpenAPI operation ids)
    overrides = [
        {
            "id": "get.health.health.check",
            "method": "GET",
            "path": "/health",
            "headers": {},
            "query": {"ping": "1"},
        },
        {
            "id": "patch.subscriptions.upgrade.to.pro",
            "method": "PATCH",
            "path": "/subscriptions/{subscription_id}/upgrade",
            "path_params": {"subscription_id": "abc-123"},
            "body": {"plan_code": "am_pro"},
        },
    ]
    out = merge_api_overrides(catalog, overrides)
    assert len(out) == 2
    assert out[0]["id"] == "health.health.get"
    assert out[0]["query"]["ping"] == "1"
    assert out[1]["id"].startswith("upgrade.subscription")
    assert out[1]["path_params"]["subscription_id"] == "abc-123"
    assert out[1]["body"]["plan_code"] == "am_pro"
