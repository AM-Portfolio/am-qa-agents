"""Batch data-gen import + suite variant expansion."""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from specs.data_gen.batch_import import import_batch, import_one_item
from specs.payloads.zip_codec import pack_zip


def test_import_batch_continues_on_failure():
    calls: list[str] = []

    def fake_import(**kwargs):
        svc = kwargs["service"]
        calls.append(svc)
        if svc == "bad-svc":
            return {"ok": False, "error": "pack_not_found", "service": svc}
        return {
            "ok": True,
            "service": svc,
            "profile": "prod",
            "payload_set_version": 3,
        }

    with patch("specs.data_gen.batch_import.import_data_gen", side_effect=fake_import):
        out = import_batch(
            [
                {"service": "am-market-data", "profile": "prod"},
                {"service": "bad-svc", "profile": "full"},
                {"service": "am-portfolio", "profile": "prod"},
            ]
        )
    assert calls == ["am-market-data", "bad-svc", "am-portfolio"]
    assert out["ok"] is False
    assert out["ok_count"] == 2
    assert out["fail_count"] == 1
    assert out["count"] == 3
    assert out["payload_set_versions"]["am-market-data:prod"] == 3
    assert out["results"][1]["ok"] is False


def test_import_batch_empty_items():
    out = import_batch([])
    assert out["ok"] is False
    assert out["error"] == "items_required"


def test_import_one_item_zip_b64(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from specs.config import settings

    settings.data_dir = str(tmp_path)

    doc = {
        "service": "am-market-data",
        "label": "data-gen-prod",
        "payload_set": {
            "service": "am-market-data",
            "label": "data-gen-prod",
            "apis": {
                "get_ipo": {
                    "api_id": "get_ipo",
                    "name": "happy-ipo",
                    "request": {"method": "GET", "path": "/v1/market-data/ipo"},
                    "response": {"status": 200},
                    "meta": {"case_kind": "happy", "expect_status": 200},
                }
            },
        },
    }
    b64 = base64.b64encode(pack_zip(doc)).decode("ascii")
    out = import_one_item(
        {
            "service": "am-market-data",
            "profile": "prod",
            "environment": "dev",
            "zip_b64": b64,
            "sync_workflows": False,
        }
    )
    assert out.get("ok") is True, out
    assert out.get("payload_set_version") is not None


def test_suite_expands_meta_variants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from specs.config import settings
    from specs.data_gen.suite import api_ids_for_suite
    from specs.payloads.payload_store import create_payload_set, get_payload_set, upsert_api_in_payload_set

    settings.data_dir = str(tmp_path)
    ps = create_payload_set("am-market-data", label="data-gen-full", make_active=True, empty=True)
    ver = int(ps["version"])
    upsert_api_in_payload_set(
        "am-market-data",
        "get_ipo",
        version=ver,
        request={"method": "GET", "path": "/v1/market-data/ipo"},
        response={"status": 200},
        meta={
            "case_kind": "must_work",
            "expect_status": 200,
            "variants": [
                {
                    "name": "tech-401",
                    "case_kind": "technical",
                    "expect_status": 401,
                    "variant_id": "unauthorized",
                    "request": {"method": "GET", "path": "/v1/market-data/ipo"},
                    "response": {"status": 401},
                }
            ],
        },
        bump_set=False,
    )

    dry = api_ids_for_suite("am-market-data", "full", version=ver, materialize_variants=False)
    assert "get_ipo" in dry["selected_api_ids"]
    assert any(x.startswith("get_ipo__v__") for x in dry["selected_api_ids"])
    assert dry["expects"].get("get_ipo__v__unauthorized") == 401

    live = api_ids_for_suite("am-market-data", "full", version=ver, materialize_variants=True)
    assert "get_ipo__v__unauthorized" in live["selected_api_ids"]
    assert "get_ipo__v__unauthorized" in (live.get("materialized_api_ids") or [])
    stored = get_payload_set("am-market-data", ver)
    assert "get_ipo__v__unauthorized" in (stored.get("apis") or {})

    default_sel = api_ids_for_suite("am-market-data", "default", version=ver)
    assert "get_ipo" in default_sel["selected_api_ids"]
    assert not any("__v__" in x for x in default_sel["selected_api_ids"])
