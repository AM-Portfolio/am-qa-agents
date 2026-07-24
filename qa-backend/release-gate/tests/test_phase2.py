"""Phase 2 observe / verify / pdf unit tests."""

import os

from am_qa_agent.intelligence.analysis import analyze_release_evidence
from am_qa_agent.intelligence.observe import annotate_deltas, collect_comparison_pack
from am_qa_agent.intelligence.pdf_dossier import publish_pdf_dossier, render_dossier_html
from am_qa_agent.intelligence.verify import post_test_verify

os.environ["QA_AGENT_SKIP_OBSERVE"] = "true"


def test_verify_passes_stub_pack():
    import asyncio

    pack = asyncio.get_event_loop().run_until_complete(
        collect_comparison_pack(services=["Market Data"])
    )
    pack = annotate_deltas(pack)
    v = post_test_verify(
        smoke={"skipped": True, "status": "COMPLETED"},
        comparisons=pack,
        gnx_mode="full",
        fin_prep={"skipped": True, "status": "STUB"},
    )
    assert v["verified"] is True
    assert v["releasable"] is True
    assert v["feature_clean"] is True


def test_verify_blocks_oom():
    pack = {
        "endpoints": [],
        "resources": [
            {
                "deployment": "am-market",
                "cpu": {"max_pct_limit": {"b": 10, "r": 20}},
                "memory": {"max_pct_limit": {"b": 10, "r": 20}},
                "oom_killed": 1,
                "restarts": {"b": 0, "r": 0},
            }
        ],
        "users": {"user_facing_5xx": {"b": 0, "r": 0}},
    }
    v = post_test_verify(smoke={"skipped": True}, comparisons=pack, gnx_mode="full")
    assert v["verified"] is False
    assert any(b.startswith("oom:") for b in v["blockers"])


def test_analysis_and_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_AGENT_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("QA_AGENT_LLM_ENABLED", "false")
    bundle = {
        "tracking_id": "qa-pdf-1",
        "gnx_mode": "full",
        "change": {"repos": ["am/am-market"]},
        "tests": {"ui_results": {"status": "COMPLETED"}},
        "comparisons": {
            "endpoints": [
                {
                    "service": "Market Data",
                    "route": "GET /health",
                    "latency_ms": {"p95": {"b": 40, "r": 45}},
                    "delta_flags": [],
                }
            ],
            "resources": [],
            "users": {},
            "unavailable": [],
        },
        "verification": {
            "verified": True,
            "releasable": True,
            "feature_clean": True,
            "infra_clean": True,
            "blockers": [],
            "warnings": [],
        },
    }
    analysis = analyze_release_evidence(bundle)
    assert analysis["recommendation"] in {"proceed", "proceed_with_warnings", "hold"}
    bundle["analysis"] = analysis
    html = render_dossier_html(bundle)
    assert "Release dossier" in html
    assert "Endpoint comparison" in html
    pub = publish_pdf_dossier(bundle, tracking_id="qa-pdf-1")
    assert pub["pdf_docs_ref"]
    assert (tmp_path / "qa-pdf-1-release-dossier.html").exists()
