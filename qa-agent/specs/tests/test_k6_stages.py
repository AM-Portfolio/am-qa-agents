"""k6 ramping-vus stages + CI presets."""

from __future__ import annotations

from specs.catalog.catalog_loader import apply_preset
from specs.load.script_generator import generate_k6_script


def test_generate_k6_script_emits_ramping_vus_when_stages_set():
    stages = [
        {"duration": "30s", "target": 1},
        {"duration": "45s", "target": 5},
        {"duration": "45s", "target": 10},
    ]
    script = generate_k6_script(
        [{"id": "a", "method": "GET", "path": "/x", "name": "a"}],
        service="am-market-data",
        vus=10,
        duration="1m",
        iterations=100,
        stages=stages,
    )
    assert "ramping-vus" in script
    assert '"target": 5' in script or '"target":5' in script
    assert "stages" in script


def test_generate_k6_script_flat_without_stages():
    script = generate_k6_script(
        [{"id": "a", "method": "GET", "path": "/x", "name": "a"}],
        service="am-market-data",
        vus=1,
        duration="1s",
        iterations=1,
        stages=None,
    )
    assert "ramping-vus" not in script
    assert "vus: 1" in script
    assert "iterations: 1" in script


def test_ci_smoke_preset():
    cfg = apply_preset({"payloads": {}}, "ci-smoke")
    assert cfg.get("dataset_profile") == "working"
    assert cfg.get("run_profile") == "debug"
    bench = (cfg.get("payloads") or {}).get("bench_run") or {}
    assert bench.get("vus") == 1
    assert bench.get("iterations") == 1
    assert not bench.get("stages")


def test_ci_load_preset_has_stages():
    cfg = apply_preset({"payloads": {}}, "ci-load")
    assert cfg.get("dataset_profile") == "full"
    assert cfg.get("run_profile") == "load"
    bench = (cfg.get("payloads") or {}).get("bench_run") or {}
    assert bench.get("iterations") == 100
    assert isinstance(bench.get("stages"), list)
    assert len(bench["stages"]) >= 2
