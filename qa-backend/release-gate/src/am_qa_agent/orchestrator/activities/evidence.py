"""Evidence activities — observe comparisons, post-test verify, analysis, PDF dossier."""

from __future__ import annotations

from temporalio import activity

from typing import Any

from am_qa_agent.intelligence.analysis import analyze_release_evidence
from am_qa_agent.intelligence.observe import annotate_deltas, collect_comparison_pack
from am_qa_agent.intelligence.pdf_dossier import publish_pdf_dossier
from am_qa_agent.intelligence.verify import post_test_verify
from am_qa_agent.stores import get_ledger


@activity.defn
async def activity_collect_comparisons(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    load_context = payload.get("load_context") or {}
    services = [s.get("name") for s in (load_context.get("fin") or {}).get("services") or [] if s.get("name")]
    routing = load_context.get("routing") or {}
    pack = await collect_comparison_pack(
        services=services,
        tool_agent_base_url=routing.get("tool_agent_base_url"),
        gnx_mcp_url=routing.get("gnx_mcp_url"),
        repo=str((load_context.get("webhook") or {}).get("repo") or ""),
    )
    pack = annotate_deltas(pack)
    get_ledger().upsert_step(tracking_id, "collect_comparisons", {"comparisons": pack})
    return pack


@activity.defn
async def activity_post_test_verify(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    matrix_results = dict(payload.get("matrix_results") or {})
    if payload.get("security"):
        matrix_results["security"] = payload["security"]
        matrix_results["sast_blockers"] = (payload["security"] or {}).get("blockers") or []
    result = post_test_verify(
        smoke=payload.get("smoke") or matrix_results,
        comparisons=payload.get("comparisons") or {},
        gnx_mode=payload.get("gnx_mode"),
        fin_prep=payload.get("fin_prep"),
        matrix_results=matrix_results,
        open_work_items=payload.get("open_work_items"),
    )
    get_ledger().upsert_step(tracking_id, "post_test_verify", result)
    return result


@activity.defn
async def activity_analyze_release(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    bundle = payload.get("bundle") or {}
    analysis = analyze_release_evidence(bundle)
    get_ledger().upsert_step(tracking_id, "analyze_release", analysis)
    return analysis


@activity.defn
async def activity_publish_pdf(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    bundle = payload.get("bundle") or {}
    pub = publish_pdf_dossier(bundle, tracking_id=tracking_id)
    # Optional MinIO / document.store
    try:
        from am_qa_agent.adapters.document_store import store_document

        stored = await store_document(
            tracking_id=tracking_id,
            local_path=str(pub.get("local_path") or pub.get("html_path")),
            content_type=str(pub.get("content_type") or "text/html"),
        )
        if stored.get("pdf_docs_ref"):
            pub["pdf_docs_ref"] = stored["pdf_docs_ref"]
            pub["store"] = stored
    except Exception as exc:  # noqa: BLE001
        pub["store_error"] = str(exc)
    get_ledger().upsert_step(tracking_id, "publish_pdf", pub)
    return pub


def build_evidence_bundle(
    *,
    tracking_id: str,
    classified: dict[str, Any],
    load_context: dict[str, Any],
    index: dict[str, Any],
    fin_prep: dict[str, Any],
    smoke: dict[str, Any],
    comparisons: dict[str, Any],
    verification: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    publication: dict[str, Any] | None = None,
    change_intent: dict[str, Any] | None = None,
    matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "release_evidence_id": f"reb-{tracking_id}",
        "tracking_id": tracking_id,
        "load_context_id": (load_context or {}).get("load_context_id"),
        "gnx_mode": (index or {}).get("gnx_mode"),
        "change": {
            "repos": [classified.get("repo")],
            "branch": classified.get("branch"),
            "head_sha": classified.get("head_sha"),
            "impact_summary": {},
            "api_contracts": [],
            "change_intent": change_intent or {},
        },
        "matrix": {
            "summary": (matrix or {}).get("summary"),
            "p0": [i.get("id") for i in ((matrix or {}).get("p0") or [])],
            "execution_plan": (matrix or {}).get("execution_plan"),
        },
        "tests": {
            "api_results": (smoke or {}).get("api") or fin_prep,
            "ui_results": (smoke or {}).get("ui") or smoke,
            "flow_results": (smoke or {}).get("flow") or {},
            "ui_report_url": (smoke or {}).get("reportUrl") or (smoke or {}).get("report_url"),
            "p0_failed": (smoke or {}).get("p0_failed") or [],
        },
        "comparisons": _merge_api_into_comparisons(comparisons, (smoke or {}).get("api") or {}),
        "verification": verification,
        "analysis": analysis or {},
        "publication": publication or {},
        "fin_prep": fin_prep,
    }


def _merge_api_into_comparisons(
    comparisons: dict[str, Any] | None,
    api: dict[str, Any] | None,
) -> dict[str, Any]:
    from am_qa_agent.intelligence.pdf_dossier import enrich_comparisons_from_api_load

    return enrich_comparisons_from_api_load(comparisons or {}, {"api_results": api or {}})
