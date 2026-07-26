"""Durable HTML report helpers when on-disk Playwright artifacts are gone."""

from __future__ import annotations

import html
import json
from typing import Any


def render_ui_report_html(
    run_id: str,
    *,
    ui_report: dict[str, Any] | None = None,
    status: str | None = None,
    service: str | None = None,
    traces: list[dict[str, Any]] | None = None,
) -> str:
    """Build a compact self-contained HTML report from DB-backed run data."""
    report = ui_report if isinstance(ui_report, dict) else {}
    steps = [t for t in (traces or []) if str(t.get("kind") or "") == "ui_step"]
    if not steps and isinstance(traces, list):
        steps = list(traces)[:50]

    profile = report.get("profile") or "UI"
    ui_status = report.get("status") or status or "unknown"
    test_id = report.get("ui_test_id") or ""
    duration = report.get("duration_ms")
    fail_n = report.get("failure_count")
    soft_n = report.get("soft_failure_count")

    rows: list[str] = []
    for t in steps:
        name = html.escape(str(t.get("name") or t.get("api_id") or "step"))
        ok = t.get("checks_passed")
        result = "PASS" if ok is True else ("FAIL" if ok is False else "—")
        color = "#15803d" if ok is True else ("#b91c1c" if ok is False else "#64748b")
        ms = ""
        timings = t.get("timings") if isinstance(t.get("timings"), dict) else {}
        if timings.get("duration_ms") is not None:
            ms = f"{timings.get('duration_ms')} ms"
        elif t.get("duration_ms") is not None:
            ms = f"{t.get('duration_ms')} ms"
        shot = t.get("screenshot_url") or ""
        shot_cell = (
            f'<a href="{html.escape(str(shot))}" target="_blank" rel="noopener">screenshot</a>'
            if shot
            else "—"
        )
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(t.get('call_index') or ''))}</td>"
            f"<td>{name}</td>"
            f"<td style='color:{color};font-weight:700'>{result}</td>"
            f"<td>{html.escape(ms)}</td>"
            f"<td>{shot_cell}</td>"
            "</tr>"
        )

    meta_bits = [
        f"<li><b>Run</b>: {html.escape(run_id)}</li>",
        f"<li><b>Profile</b>: {html.escape(str(profile))}</li>",
        f"<li><b>Status</b>: {html.escape(str(ui_status))}</li>",
    ]
    if service:
        meta_bits.append(f"<li><b>Service</b>: {html.escape(str(service))}</li>")
    if test_id:
        meta_bits.append(f"<li><b>UI test id</b>: {html.escape(str(test_id))}</li>")
    if duration is not None:
        meta_bits.append(f"<li><b>Duration</b>: {html.escape(str(duration))} ms</li>")
    if fail_n is not None:
        meta_bits.append(f"<li><b>Failures</b>: {html.escape(str(fail_n))}</li>")
    if soft_n is not None:
        meta_bits.append(f"<li><b>Soft failures</b>: {html.escape(str(soft_n))}</li>")

    llm = report.get("llm_report")
    llm_block = ""
    if isinstance(llm, dict) and llm:
        llm_block = (
            "<h2>LLM summary</h2>"
            f"<pre>{html.escape(json.dumps(llm, indent=2, default=str)[:8000])}</pre>"
        )

    design = report.get("design_review")
    design_block = ""
    if isinstance(design, dict) and design:
        design_block = (
            "<h2>Design review</h2>"
            f"<pre>{html.escape(json.dumps(design, indent=2, default=str)[:4000])}</pre>"
        )

    console = report.get("console_errors") or []
    console_block = ""
    if console:
        items = "".join(f"<li>{html.escape(str(c))}</li>" for c in console[:20])
        console_block = f"<h2>Console errors</h2><ul>{items}</ul>"

    note = (
        "<p class='note'>This is the durable SPT report (survives pod restarts). "
        "Full Playwright HTML/PDF may be unavailable after ephemeral disk wipe.</p>"
    )

    table = (
        "<table><thead><tr>"
        "<th>#</th><th>Step</th><th>Result</th><th>Time</th><th>Evidence</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows) if rows else '<tr><td colspan=5>No UI steps in stored traces</td></tr>'}"
        "</tbody></table>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>UI report · {html.escape(run_id)}</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, Segoe UI, sans-serif; margin: 2rem; color: #0f172a; }}
    h1 {{ font-size: 1.4rem; margin-bottom: 0.4rem; }}
    .note {{ color: #64748b; font-size: 0.9rem; }}
    ul {{ line-height: 1.5; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 0.45rem 0.6rem; text-align: left; font-size: 0.92rem; }}
    th {{ background: #f8fafc; }}
    pre {{ background: #f8fafc; padding: 0.75rem; overflow: auto; border-radius: 6px; font-size: 0.8rem; }}
    a {{ color: #1d4ed8; }}
  </style>
</head>
<body>
  <h1>Playwright / UI report</h1>
  {note}
  <ul>{''.join(meta_bits)}</ul>
  <h2>Steps</h2>
  {table}
  {llm_block}
  {design_block}
  {console_block}
</body>
</html>
"""
