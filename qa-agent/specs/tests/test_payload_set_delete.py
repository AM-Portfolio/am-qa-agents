"""Payload-set remove APIs + delete entire version."""
from __future__ import annotations

from pathlib import Path

import pytest

from specs.payloads import payload_store as ps


@pytest.fixture()
def payload_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(ps.settings, "data_dir", str(data))
    return data


def test_remove_apis_and_delete_version(payload_root: Path):
    created = ps.create_payload_set("svc-a", label="t", make_active=True, empty=True)
    ver = int(created["version"])
    ps.upsert_api_in_payload_set(
        "svc-a",
        "api.one",
        version=ver,
        request={"method": "GET", "path": "/one"},
    )
    ps.upsert_api_in_payload_set(
        "svc-a",
        "api.two",
        version=ver,
        request={"method": "POST", "path": "/two"},
    )
    row = ps.get_payload_set("svc-a", ver)
    assert row and set((row.get("apis") or {}).keys()) == {"api.one", "api.two"}

    out = ps.remove_apis_from_payload_set("svc-a", ver, ["api.one"])
    assert out["removed"] == ["api.one"]
    assert out["api_count"] == 1
    row2 = ps.get_payload_set("svc-a", ver)
    assert row2 and list((row2.get("apis") or {}).keys()) == ["api.two"]

    v2 = ps.create_payload_set("svc-a", label="t2", clone_from=ver, make_active=True)
    ver2 = int(v2["version"])
    deleted = ps.delete_payload_set("svc-a", ver)
    assert deleted["deleted"] is True
    assert ps.get_payload_set("svc-a", ver) is None
    meta = ps.list_payload_sets("svc-a")
    assert meta["active_version"] == ver2
    assert all(int(s["version"]) != ver for s in meta["sets"])

    ps.delete_payload_set("svc-a", ver2)
    meta2 = ps.list_payload_sets("svc-a")
    assert meta2["active_version"] is None
    assert meta2["count"] == 0


def test_delete_missing_raises(payload_root: Path):
    with pytest.raises(FileNotFoundError):
        ps.delete_payload_set("missing", 1)
    with pytest.raises(FileNotFoundError):
        ps.remove_apis_from_payload_set("missing", 1, ["x"])
