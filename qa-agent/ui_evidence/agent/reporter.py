from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig

from ui_evidence.agent.design_status import compute_final_status, should_fail_run
from ui_evidence.agent.report_llm import generate_llm_report
from ui_evidence.agent.report_metrics import build_report_document, render_report_html, write_baseline_bundle
from ui_evidence.agent.report_pdf import write_report_pdf
from ui_evidence.agent.state import AutonomousAgentState
from ui_evidence.config import settings
from ui_evidence.context import get_test_context

logger = logging.getLogger(__name__)


async def reporter_node(state: AutonomousAgentState, config: RunnableConfig) -> dict[str, Any]:
    ctx = get_test_context(config)
    status = compute_final_status(state)
    failures = state.get("failures_encountered") or []

    report_dir = Path(settings.REPORT_DIR)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{ctx.test_id}.html"
    json_path = report_dir / f"{ctx.test_id}.json"
    pdf_path = report_dir / f"{ctx.test_id}.pdf"

    screenshots = state.get("screenshot_history") or []
    labels = state.get("screenshot_labels") or []
    prefix = (ctx.profile or "ui").split("_")[0].lower()
    try:
        from ui_evidence.browser.evidence_paths import profile_evidence_prefix

        prefix = profile_evidence_prefix(ctx.profile)
    except Exception:
        pass
    evidence_dir = ctx.evidence_dirname or ""
    img_html = ""
    if evidence_dir:
        img_html += (
            f'<p><strong>Screenshot folder:</strong> '
            f'<code>screenshots/{html.escape(evidence_dir)}</code></p>'
        )
    for i, shot in enumerate(screenshots):
        label = html.escape(labels[i] if i < len(labels) else f"Screenshot {i + 1}")
        timing = next(
            (t for t in ctx.step_timings if t.get("index") == i + 1),
            None,
        )
        file_hint = ""
        if timing and timing.get("screenshot_file"):
            file_hint = Path(str(timing["screenshot_file"])).name
        heading = f"[{html.escape(prefix)}] {label}"
        if file_hint:
            heading = (
                f"{heading} "
                f"<span style='color:#64748b;font-weight:normal'>({html.escape(file_hint)})</span>"
            )
        img_html += f"<h3>{heading}</h3><img src=\"data:image/png;base64,{shot}\"/>"

    document = build_report_document(
        ctx=ctx,
        state=state,
        status=status,
        report_path=str(report_path.resolve()),
    )

    final_shot = screenshots[-1] if screenshots else None
    document["llm_report"] = await generate_llm_report(
        ctx,
        document,
        llm_client=ctx.llm_client,
        final_screenshot_b64=final_shot,
    )
    ctx.log_action(
        "llm_report",
        generated=document["llm_report"].get("generated"),
        model=document["llm_report"].get("model"),
    )

    body = render_report_html(document, screenshots_html=img_html)

    report_path.write_text(body, encoding="utf-8")
    json_path.write_text(json.dumps(document, indent=2, default=str), encoding="utf-8")

    pdf_written = await write_report_pdf(html_path=report_path, pdf_path=pdf_path)
    if pdf_written:
        document["report_pdf"] = str(pdf_written.resolve())
        json_path.write_text(json.dumps(document, indent=2, default=str), encoding="utf-8")
        ctx.log_action("report_pdf", path=str(pdf_written), status=status)

    bundle_dir = write_baseline_bundle(test_id=ctx.test_id, document=document)
    if bundle_dir:
        logger.info("Baseline bundle written → %s", bundle_dir)
    logger.info("Report written → %s (%s)", report_path, status)
    ctx.log_action("report", path=str(report_path), status=status)

    if should_fail_run(status):
        raise RuntimeError(f"Test failed ({status}) with {len(failures)} failure(s). Report: {report_path}")

    return {"report_output": str(report_path)}
