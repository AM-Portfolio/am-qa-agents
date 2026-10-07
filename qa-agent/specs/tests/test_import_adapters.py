"""Postman → AmImportBundle → payload set."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specs.import_adapters import import_collection_to_payload_set, list_formats
from specs.import_adapters.postman_v2 import PostmanV2Adapter
from specs.import_adapters.registry import get_adapter


SAMPLE_COLLECTION = {
    "info": {
        "name": "Subscription Sample",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "item": [
        {
            "name": "Plans",
            "item": [
                {
                    "name": "List plans",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "Accept", "value": "application/json"}],
                        "url": {
                            "raw": "{{baseUrl}}/subscriptions/plans",
                            "host": ["{{baseUrl}}"],
                            "path": ["subscriptions", "plans"],
                        },
                    },
                }
            ],
        },
        {
            "name": "Create",
            "request": {
                "method": "POST",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": {"mode": "raw", "raw": '{"plan_code":"{{plan}}"}'},
                "url": "{{baseUrl}}/subscriptions",
            },
        },
    ],
}

SAMPLE_ENV = {
    "name": "dev",
    "_postman_variable_scope": "environment",
    "values": [
        {"key": "baseUrl", "value": "https://am-dev.asrax.in", "enabled": True},
        {"key": "plan", "value": "am_free", "enabled": True},
    ],
}


def test_list_formats_includes_postman():
    assert "postman" in list_formats()


def test_postman_detect_and_parse():
    adapter = PostmanV2Adapter()
    assert adapter.detect(SAMPLE_COLLECTION)
    bundle = adapter.parse_collection(SAMPLE_COLLECTION, service="am-subscription")
    assert bundle.source == "postman"
    assert len(bundle.items) == 2
    assert bundle.items[0].method == "GET"
    assert "/subscriptions/plans" in bundle.items[0].path


def test_registry_rejects_unknown_format():
    with pytest.raises(ValueError, match="Unsupported"):
        get_adapter("bruno-not-yet")


def test_import_writes_payload_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from specs.config import settings

    settings.data_dir = str(tmp_path)
    out = import_collection_to_payload_set(
        service="am-subscription",
        collection=SAMPLE_COLLECTION,
        environment=SAMPLE_ENV,
        format="postman",
        make_active=True,
        bump_set=True,
    )
    assert out["ok"] is True
    assert out["imported"] == 2
    assert out["payload_set_version"] >= 1
    set_path = tmp_path / "payloads" / "sets" / "am-subscription" / f"v{out['payload_set_version']}.json"
    data = json.loads(set_path.read_text(encoding="utf-8"))
    apis = data["apis"]
    assert any("/subscriptions/plans" in (v.get("request") or {}).get("path", "") for v in apis.values())
    # env substitution applied
    create = next(v for v in apis.values() if (v.get("request") or {}).get("method") == "POST")
    assert create["request"]["body"] == {"plan_code": "am_free"}
    assert create["request"]["path"] == "/subscriptions"


def test_merge_strips_base_url_and_keeps_path_params():
    from specs.import_adapters.base import AmImportBundle, AmImportItem, merge_bundle_env

    bundle = AmImportBundle(
        source="postman",
        service="am-subscription",
        label="t",
        items=[
            AmImportItem(
                api_id="cancel",
                name="Cancel",
                method="PATCH",
                path="/{{base_url}}/subscriptions/{{subscription_id}}/cancel",
            )
        ],
    )
    out = merge_bundle_env(
        bundle,
        {
            "base_url": "https://am-dev.asrax.in",
            "subscription_id": "abc-123",
        },
    )
    assert out.items[0].path == "/subscriptions/{subscription_id}/cancel"
    assert out.items[0].path_params.get("subscription_id") == "abc-123"
