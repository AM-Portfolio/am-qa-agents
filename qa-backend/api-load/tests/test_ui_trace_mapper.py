"""Unit tests for ui-test-agent → SPT trace mapping."""
from __future__ import annotations

from app.ui_trace_mapper import agent_status_passed, map_status_to_traces


def test_map_step_timings_to_traces():
    status = {
        "testId": "abc",
        "status": "COMPLETED",
        "profile": "PORTFOLIO_SMOKE_FLOW",
        "targetUrl": "http://localhost:9000",
        "step_timings": [
            {
                "index": 1,
                "name": "login",
                "action": "click",
                "phase": "execute",
                "duration_ms": 120.5,
                "status": "ok",
            },
            {
                "index": 2,
                "name": "open_portfolio",
                "action": "goto",
                "phase": "execute",
                "duration_ms": 80,
                "status": "ok",
            },
        ],
        "action_log": [{"action": "click", "step": "login", "ts": "t"}],
        "failures": [],
        "reportUrl": "/api/v1/test/report/abc",
    }
    traces, index, summary = map_status_to_traces(status)
    assert len(traces) == 2
    assert traces[0]["kind"] == "ui_step"
    assert traces[0]["method"] == "CLICK"
    assert traces[0]["checks_passed"] is True
    assert traces[0]["timings"]["duration_ms"] == 120.5
    assert len(index) == 2
    assert summary["kind"] == "profile"
    assert summary["ui_test_id"] == "abc"
    assert agent_status_passed(status) is True


def test_map_failures_mark_step_failed():
    status = {
        "status": "FAILED",
        "profile": "AUTH_FLOW",
        "step_timings": [
            {
                "index": 1,
                "name": "assert_dashboard",
                "action": "assert",
                "phase": "assert",
                "duration_ms": 10,
                "status": "error",
                "error": "selector missing",
            }
        ],
        "failures": [{"error": "selector missing"}],
    }
    traces, index, _ = map_status_to_traces(status)
    assert traces[0]["checks_passed"] is False
    assert index[0]["fail_count"] == 1
    assert agent_status_passed(status) is False


def test_map_suite_results():
    status = {
        "testId": "suite-1",
        "status": "COMPLETED",
        "decision": "GO",
        "suite": "smoke",
        "targetUrl": "http://ui",
        "results": [
            {"profile": "DASHBOARD_SMOKE_FLOW", "status": "COMPLETED", "duration_ms": 1000},
            {
                "profile": "PORTFOLIO_SMOKE_FLOW",
                "status": "FAILED",
                "error": "boom",
                "duration_ms": 500,
            },
        ],
    }
    traces, index, summary = map_status_to_traces(status)
    assert summary["kind"] == "suite"
    assert len(traces) == 2
    assert traces[0]["checks_passed"] is True
    assert traces[1]["checks_passed"] is False
    assert len(index) == 2


def test_map_empty_status_single_row():
    status = {"status": "COMPLETED", "profile": "AUTH_FLOW_MAIN", "duration_ms": 42}
    traces, index, _ = map_status_to_traces(status)
    assert len(traces) == 1
    assert traces[0]["name"] == "AUTH_FLOW_MAIN"
    assert len(index) == 1
