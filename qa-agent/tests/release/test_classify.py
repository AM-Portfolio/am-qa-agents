"""Classify unit tests — Phase 0."""

from intelligence import classify_trigger, idempotency_key


def test_ci_success_qa_route():
    r = classify_trigger(
        {
            "repo": "am/am-market",
            "branch": "feature/x",
            "head_sha": "abc123",
            "ci_conclusion": "success",
        }
    )
    assert r.route == "qa-route"
    assert r.reason == "ci_success"


def test_ci_failure_dev_route():
    r = classify_trigger(
        {
            "repo": "am/am-market",
            "branch": "feature/x",
            "head_sha": "abc123",
            "ci_conclusion": "failure",
        }
    )
    assert r.route == "dev-route"
    assert "failure" in r.reason


def test_workflow_run_shape():
    r = classify_trigger(
        {
            "repository": {"full_name": "am/am-modern-ui"},
            "workflow_run": {
                "conclusion": "success",
                "head_sha": "deadbeef",
                "head_branch": "main",
            },
        }
    )
    assert r.route == "qa-route"
    assert r.repo == "am/am-modern-ui"
    assert r.head_sha == "deadbeef"


def test_idempotency_stable():
    p = {
        "repo": "am/am-market",
        "head_sha": "abc",
        "trigger_kind": "manual",
        "ci_conclusion": "success",
        "branch": "main",
    }
    assert idempotency_key(p) == idempotency_key(p)
