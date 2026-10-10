"""expect_status → k6 checks and api_summary outcome (pass|expected|fail)."""

from __future__ import annotations

from specs.catalog.catalog_loader import checks_for_expect_status
from specs.persistence.trace_store import api_outcome, build_api_index, summarize_api_outcomes


def test_checks_for_expect_status_2xx():
    assert checks_for_expect_status(200) == ["status_2xx"]
    assert checks_for_expect_status(201) == ["status_2xx"]
    assert checks_for_expect_status(None) == ["status_2xx"]


def test_checks_for_expect_status_401():
    assert checks_for_expect_status(401) == ["status_401"]
    assert checks_for_expect_status(400) == ["status_400"]
    assert checks_for_expect_status(403) == ["status_403"]


def test_api_outcome_pass_expected_fail():
    assert api_outcome(expect_status=200, checks_passed=True) == "pass"
    assert api_outcome(expect_status=401, checks_passed=True) == "expected"
    assert api_outcome(expect_status=401, checks_passed=False) == "fail"
    assert api_outcome(expect_status=200, checks_passed=False) == "fail"
    assert api_outcome(expect_status=200, checks_passed=None) == "pending"


def test_build_api_index_outcome_expected():
    apis = [
        {
            "id": "tech_auth",
            "name": "tech_auth",
            "method": "GET",
            "path": "/secret",
            "expect_status": 401,
            "case_kind": "technical",
            "checks": ["status_401"],
        }
    ]
    traces = [
        {
            "api_id": "tech_auth",
            "name": "tech_auth",
            "method": "GET",
            "checks_passed": True,
            "response": {"status": 401},
            "timings": {"duration_ms": 12},
        }
    ]
    index = build_api_index(traces, {}, apis)
    assert len(index) == 1
    assert index[0]["expect_status"] == 401
    assert index[0]["case_kind"] == "technical"
    assert index[0]["outcome"] == "expected"
    counts = summarize_api_outcomes(index)
    assert counts["api_pass_count"] == 0
    assert counts["api_expected_count"] == 1
    assert counts["api_unexpected_fail_count"] == 0
