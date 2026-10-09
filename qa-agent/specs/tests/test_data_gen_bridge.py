"""am-specs data-gen → Specs bridge (adapter, branch, prefer, suite filter, workflows)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specs.data_gen.branch import (
    resolve_branch_defaults,
    resolve_data_gen_environment,
    resolve_data_gen_profile,
)
from specs.data_gen.prefer import collapse_by_api_id, expect_status_of
from specs.import_adapters import import_collection_to_payload_set, list_formats
from specs.import_adapters.am_specs_dataset import AmSpecsDatasetAdapter
from specs.import_adapters.registry import get_adapter


SAMPLE_PAYLOAD_SET = {
    "service": "am-market-data",
    "label": "data-gen-prod",
    "source": {"kind": "am-specs-datasets", "profile": "prod", "dataset_version": 1},
    "apis": {
        "get_v1_market-data_ipo": {
            "api_id": "get_v1_market-data_ipo",
            "name": "happy-ipo",
            "request": {
                "method": "GET",
                "path": "/v1/market-data/ipo",
                "query": {"status": "open"},
                "path_params": {},
                "headers": {},
                "body": None,
            },
            "response": {"status": 200},
            "meta": {"case_kind": "happy", "variant_id": "happy-ipo"},
        },
        "get_v1_fundamentals_symbol": {
            "api_id": "get_v1_fundamentals_symbol",
            "name": "mw-fundamentals",
            "request": {
                "method": "GET",
                "path": "/v1/fundamentals/{{symbol}}",
                "query": {},
                "path_params": {"symbol": "{{symbol}}"},
                "headers": {},
                "body": None,
            },
            "response": {"status": 200},
            "meta": {"case_kind": "must_work", "variant_id": "mw-fundamentals"},
        },
    },
}


def test_list_formats_includes_am_specs_dataset():
    assert "am-specs-dataset" in list_formats()


def test_adapter_detect_and_parse():
    adapter = AmSpecsDatasetAdapter()
    wrapped = {
        "format": "am-specs-dataset",
        "service": "am-market-data",
        "payload_set": SAMPLE_PAYLOAD_SET,
    }
    assert adapter.detect(wrapped)
    assert get_adapter("am-specs-dataset").format_id == "am-specs-dataset"
    bundle = adapter.parse_collection(wrapped, service="am-market-data")
    assert bundle.service == "am-market-data"
    assert len(bundle.items) == 2
    assert any(i.path.endswith("/ipo") for i in bundle.items)


def test_collapse_prefers_must_work():
    rows = [
        {
            "api_id": "x",
            "request": {"method": "GET", "path": "/x"},
            "meta": {"case_kind": "technical", "variant_id": "tech"},
            "response": {"status": 401},
        },
        {
            "api_id": "x",
            "request": {"method": "GET", "path": "/x"},
            "meta": {"case_kind": "must_work", "variant_id": "mw"},
            "response": {"status": 200},
        },
        {
            "api_id": "x",
            "request": {"method": "GET", "path": "/x"},
            "meta": {"case_kind": "happy", "variant_id": "h"},
            "response": {"status": 200},
        },
    ]
    out = collapse_by_api_id(rows)
    assert out["x"]["meta"]["case_kind"] == "must_work"
    assert len(out["x"]["meta"]["variants"]) == 2
    assert expect_status_of(out["x"]) == 200


def test_branch_defaults():
    assert resolve_data_gen_profile("refs/heads/develop") == "default"
    assert resolve_data_gen_profile("hotfix/urgent") == "default"
    assert resolve_data_gen_profile("main") == "default"
    assert resolve_data_gen_profile("main", explicit="full") == "full"
    assert resolve_data_gen_environment("develop") == "dev"
    assert resolve_data_gen_environment("main") == "preprod"
    assert resolve_data_gen_environment("hotfix/x") == "preprod"
    d = resolve_branch_defaults(git_ref="feature/foo")
    assert d["suite"] == "default"
    assert d["environment"] == "dev"


def test_import_writes_payload_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from specs.config import settings

    settings.data_dir = str(tmp_path)
    out = import_collection_to_payload_set(
        service="am-market-data",
        collection={
            "format": "am-specs-dataset",
            "service": "am-market-data",
            "payload_set": SAMPLE_PAYLOAD_SET,
        },
        format="am-specs-dataset",
        label="data-gen-prod",
        make_active=True,
        bump_set=True,
    )
    assert out["ok"] is True
    assert out["imported"] == 2
    set_path = (
        tmp_path / "payloads" / "sets" / "am-market-data" / f"v{out['payload_set_version']}.json"
    )
    data = json.loads(set_path.read_text(encoding="utf-8"))
    apis = data["apis"]
    assert "get_v1_market-data_ipo" in apis
    meta = apis["get_v1_market-data_ipo"].get("meta") or {}
    assert meta.get("case_kind") == "happy"
    assert meta.get("expect_status") == 200


def test_empty_import_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from specs.config import settings

    settings.data_dir = str(tmp_path)
    out = import_collection_to_payload_set(
        service="am-market-data",
        collection={
            "format": "am-specs-dataset",
            "payload_set": {
                "service": "am-market-data",
                "source": {"kind": "am-specs-datasets", "profile": "prod"},
                "apis": {},
            },
        },
        format="am-specs-dataset",
        bump_set=True,
    )
    assert out["ok"] is False
    assert out["imported"] == 0


def test_suite_api_ids_excludes_cross_flow_and_tech_without_expect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from specs.config import settings
    from specs.data_gen.suite import api_ids_for_suite
    from specs.payloads.payload_store import create_payload_set, upsert_api_in_payload_set

    settings.data_dir = str(tmp_path)
    ps = create_payload_set("am-market-data", label="data-gen-prod", make_active=True, empty=True)
    ver = int(ps["version"])
    upsert_api_in_payload_set(
        "am-market-data",
        "happy1",
        version=ver,
        request={"method": "GET", "path": "/a"},
        response={"status": 200},
        meta={"case_kind": "happy", "expect_status": 200},
        bump_set=False,
    )
    upsert_api_in_payload_set(
        "am-market-data",
        "cross1",
        version=ver,
        request={"method": "GET", "path": "/b"},
        response={"status": 200},
        meta={"case_kind": "cross_flow"},
        bump_set=False,
    )
    upsert_api_in_payload_set(
        "am-market-data",
        "tech1",
        version=ver,
        request={"method": "GET", "path": "/c"},
        response={},
        meta={"case_kind": "technical"},
        bump_set=False,
    )
    upsert_api_in_payload_set(
        "am-market-data",
        "tech2",
        version=ver,
        request={"method": "GET", "path": "/d"},
        response={"status": 401},
        meta={"case_kind": "technical", "expect_status": 401},
        bump_set=False,
    )
    default_sel = api_ids_for_suite("am-market-data", "default", version=ver)
    assert "happy1" in default_sel["selected_api_ids"]
    assert "cross1" not in default_sel["selected_api_ids"]
    assert "tech1" not in default_sel["selected_api_ids"]

    full_sel = api_ids_for_suite("am-market-data", "full", version=ver)
    assert "tech2" in full_sel["selected_api_ids"]
    assert full_sel["expects"]["tech2"] == 401
    assert "tech1" not in full_sel["selected_api_ids"]
    assert any("expect_status" in w for w in full_sel["warnings"])


def test_workflow_sync_and_prune(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from specs.config import settings
    from specs.data_gen.workflows import list_data_gen_workflows, sync_cross_flow_workflows

    settings.data_dir = str(tmp_path)
    examples = [
        {
            "api_id": "a",
            "name": "step1",
            "request": {"method": "GET", "path": "/v1/watchlists"},
            "meta": {
                "case_kind": "cross_flow",
                "flow_id": "watchlist_ltp",
                "flow_step": 1,
                "variant_id": "wl-list",
            },
            "response": {"status": 200},
        },
        {
            "api_id": "b",
            "name": "step2",
            "request": {"method": "GET", "path": "/v1/market-data/ltp"},
            "meta": {
                "case_kind": "cross_flow",
                "flow_id": "watchlist_ltp",
                "flow_step": 2,
                "variant_id": "ltp",
            },
            "response": {"status": 200},
        },
    ]
    out = sync_cross_flow_workflows(
        service="am-market-data", profile="prod", examples=examples, payload_set_version=1
    )
    assert out["count"] == 1
    assert out["upserted"]
    rows = list_data_gen_workflows(service="am-market-data", profile="prod")
    assert len(rows) >= 1

    # prune when flow gone
    out2 = sync_cross_flow_workflows(
        service="am-market-data", profile="prod", examples=[], prune=True
    )
    assert out["upserted"][0] in out2["pruned"]
