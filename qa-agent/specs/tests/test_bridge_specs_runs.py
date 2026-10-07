"""Bridge suite profile → Specs traces / api_summary."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ui_evidence.bridge_specs_runs import (
    build_enriched_ui_evidence,
    ui_status_passed,
)


def test_ui_status_passed_allowlist():
    assert ui_status_passed("PASSED")
    assert ui_status_passed("COMPLETED")
    assert ui_status_passed("GO_WITH_CAVEATS")
    assert not ui_status_passed("FAILED")
    assert not ui_status_passed("NO_GO")


def test_build_enriched_ui_evidence_from_step_timings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report = {
        "test_id": "t-bridge-1",
        "profile": "AUTH_REG_FILL",
        "status": "PASSED",
        "target_url": "https://am.asrax.in",
        "step_timings": [
            {
                "index": 1,
                "name": "open_register",
                "action": "navigate",
                "phase": "execute",
                "duration_ms": 10,
                "status": "ok",
            },
            {
                "index": 2,
                "name": "fill_email",
                "action": "fill",
                "phase": "execute",
                "duration_ms": 5,
                "status": "ok",
            },
            {
                "index": 3,
                "name": "assert_button",
                "action": "assert",
                "phase": "assert",
                "duration_ms": 2,
                "status": "ok",
            },
        ],
        "action_log": [],
        "results": {"checklist": [{"id": "c1", "pass": True}], "failures": []},
        "timing": {"total_duration_ms": 17},
    }
    html = tmp_path / "a95b-AUTH_REG_FILL.html"
    html.write_text("<html></html>", encoding="utf-8")
    html.with_suffix(".json").write_text(json.dumps(report), encoding="utf-8")

    data_dir = tmp_path / "spt-data"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    try:
        from specs.config import settings

        monkeypatch.setattr(settings, "data_dir", str(data_dir), raising=False)
    except Exception:
        pass

    run_id = "relops-qa-test-AUTH_REG_FILL"
    ev = build_enriched_ui_evidence(
        {"profile": "AUTH_REG_FILL", "status": "PASSED", "report": str(html)},
        run_id=run_id,
        profile="AUTH_REG_FILL",
        target_url="https://am.asrax.in",
    )
    assert ev["passed"] is True
    assert ev["api_count"] == 3
    assert ev["api_pass_count"] == 3
    assert ev["api_fail_count"] == 0
    assert len(ev["api_summary"]) == 3
    traces_path = data_dir / "artifacts" / run_id / "traces.json"
    assert traces_path.is_file()
    traces = json.loads(traces_path.read_text(encoding="utf-8"))
    assert len(traces) == 3
    assert traces[0]["kind"] == "ui_step"
    assert (ev["ui_report"] or {}).get("step_timings")
