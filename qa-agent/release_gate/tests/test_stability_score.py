"""Unit tests for stability score + Cliq final body."""
from __future__ import annotations

from intelligence.cliq_final import build_cliq_final_body
from intelligence.stability_score import (
    band_for_score,
    compute_stability,
    score_alerts,
    score_business,
    score_technical,
)


def test_band_thresholds():
    assert band_for_score(95) == "STABLE"
    assert band_for_score(80) == "ACCEPTABLE"
    assert band_for_score(60) == "AT_RISK"
    assert band_for_score(10) == "UNSTABLE"


def test_perfect_score_stable():
    tech = score_technical(
        {"p95_ok": True, "cpu_ok": True, "mem_ok": True, "restart_ok": True, "error_ok": True}
    )
    alerts = score_alerts([])
    biz = score_business([{"id": "a", "ok": True, "weight": 1}])
    out = compute_stability(technical=tech, alerts=alerts, business=biz, release_id="r1")
    assert out["stability_score"] == 100
    assert out["band"] == "STABLE"
    assert out["system_stable"] is True


def test_critical_alert_cuts_score():
    tech = score_technical(
        {"p95_ok": True, "cpu_ok": True, "mem_ok": True, "restart_ok": True, "error_ok": True}
    )
    alerts = score_alerts([{"severity": "critical", "name": "disk"}])
    biz = score_business([{"id": "a", "ok": True, "weight": 1}])
    out = compute_stability(technical=tech, alerts=alerts, business=biz)
    assert out["pillars"]["alerts"]["score"] == 15
    assert out["stability_score"] == 85
    assert out["band"] == "ACCEPTABLE"


def test_unavailable_caps_stable():
    tech = score_technical({}, unavailable=True)
    alerts = score_alerts([])
    biz = score_business([{"id": "a", "ok": True, "weight": 1}])
    out = compute_stability(technical=tech, alerts=alerts, business=biz)
    assert out["any_unavailable"] is True
    assert out["band"] != "STABLE"


def test_cliq_body_contains_links_and_band():
    stability = compute_stability(
        technical=score_technical(
            {"p95_ok": True, "cpu_ok": True, "mem_ok": True, "restart_ok": True, "error_ok": True}
        ),
        alerts=score_alerts([]),
        business=score_business([{"id": "a", "ok": True, "weight": 1}]),
        release_id="asrax-r01-test",
        soak_minutes=30,
    )
    body = build_cliq_final_body(
        release_name="Release 01",
        stability=stability,
        ui_decision="GO",
        sheet_url="https://docs.google.com/spreadsheets/d/x",
        drive_links={
            "master_pdf": "https://drive.google.com/file/d/master",
            "final_pdf": "https://drive.google.com/file/d/1",
            "folder": "https://drive.google.com/drive/folders/f",
        },
        grafana_url="https://grafana.example/d/soak",
    )
    assert "FINAL (STABLE)" in body
    assert "https://docs.google.com/spreadsheets/d/x" in body
    assert "https://drive.google.com/file/d/master" in body
    assert "https://drive.google.com/drive/folders/f" in body
    assert "https://grafana.example/d/soak" in body
    assert "asrax-r01-test" in body
    assert "MinIO" in body
