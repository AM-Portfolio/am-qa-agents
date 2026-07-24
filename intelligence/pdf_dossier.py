"""PDF / HTML release dossier — readable evidence, not empty dumps."""

from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _esc(v: Any) -> str:
    return html.escape(str(v if v is not None else ""))


def _rows_api_load(tests: dict[str, Any]) -> str:
    api = tests.get("api_results") or {}
    services = api.get("services") or []
    if not services:
        return '<tr><td colspan="7">No API load results</td></tr>'
    rows: list[str] = []
    for svc in services:
        name = svc.get("name") or "?"
        for scen, detail in (svc.get("scenarios") or {}).items():
            if not isinstance(detail, dict):
                continue
            lat_raw = detail.get("latency_ms")
            lat = lat_raw if isinstance(lat_raw, dict) else {"p50": lat_raw, "p95": None}
            codes = detail.get("status_codes") or detail.get("status_code") or {}
            rows.append(
                "<tr>"
                f"<td>{_esc(name)}</td>"
                f"<td>{_esc(scen)}</td>"
                f"<td>{_esc('PASS' if detail.get('ok') else 'FAIL')}</td>"
                f"<td>{_esc(detail.get('url') or svc.get('health_url') or '')}</td>"
                f"<td>{_esc(lat.get('p50'))}</td>"
                f"<td>{_esc(lat.get('p95'))}</td>"
                f"<td>{_esc(codes)}</td>"
                "</tr>"
            )
    return "".join(rows) or '<tr><td colspan="7">No scenarios</td></tr>'


def _change_summary(change: dict[str, Any]) -> str:
    intent = change.get("change_intent") or {}
    if not intent and not change:
        return "<p><i>No change context</i></p>"
    risks = intent.get("risk_hypotheses") or []
    focus = intent.get("suggested_test_focus") or []
    return f"""
<p><b>Repo:</b> {_esc((change.get('repos') or [None])[0])} @ {_esc(change.get('branch'))}<br/>
<b>SHA:</b> {_esc(change.get('head_sha'))}<br/>
<b>Goal:</b> {_esc(intent.get('user_goal') or '—')}<br/>
<b>Scope:</b> {_esc(intent.get('author_stated_scope') or '—')}</p>
<p><b>Risks:</b> {_esc('; '.join(str(r) for r in risks) if risks else 'none')}</p>
<p><b>Test focus:</b> {_esc(focus if focus else 'none')}</p>
"""


def _ui_summary(tests: dict[str, Any]) -> str:
    ui = tests.get("ui_results") or {}
    return (
        f"<p><b>UI:</b> status={_esc(ui.get('status'))} mode={_esc(ui.get('mode'))} "
        f"profile={_esc(ui.get('profile'))} skipped={_esc(ui.get('skipped'))}</p>"
        f"<p><b>API:</b> status={_esc((tests.get('api_results') or {}).get('status'))} "
        f"mode={_esc((tests.get('api_results') or {}).get('mode'))} "
        f"load={_esc((tests.get('api_results') or {}).get('load'))} "
        f"passed={_esc((tests.get('api_results') or {}).get('passed'))} "
        f"failed={_esc((tests.get('api_results') or {}).get('failed'))}</p>"
        f"<p><b>P0 failed:</b> {_esc(tests.get('p0_failed') or [])}</p>"
    )


def enrich_comparisons_from_api_load(
    comparisons: dict[str, Any],
    tests: dict[str, Any],
) -> dict[str, Any]:
    """If Grafana observe is empty, show API load latencies in endpoint table."""
    out = dict(comparisons or {})
    existing = out.get("endpoints") or []
    # Keep observe rows that are real (not only template noise) when present;
    # still append api_load rows when we have live API results.
    api = (tests or {}).get("api_results") or {}
    api_rows: list[dict[str, Any]] = []
    for svc in api.get("services") or []:
        health = (svc.get("scenarios") or {}).get("health_smoke") or {}
        lat = health.get("latency_ms") or {}
        if not health:
            continue
        api_rows.append(
            {
                "service": svc.get("name"),
                "route": svc.get("health_url") or "health_smoke",
                "latency_ms": {
                    "p50": {"b": "—", "r": lat.get("p50")},
                    "p95": {"b": "—", "r": lat.get("p95")},
                },
                "delta_flags": ["api_load"],
                "source": "api_load",
                "ok": health.get("ok"),
            }
        )
    if api_rows:
        # Prefer api_load when observe is template-only empty flags
        if not existing or all((e.get("source") == "template") for e in existing):
            out["endpoints"] = api_rows
        else:
            out["endpoints"] = list(existing) + api_rows
    return out


def render_dossier_html(bundle: dict[str, Any]) -> str:
    analysis = bundle.get("analysis") or {}
    verification = bundle.get("verification") or {}
    tests = bundle.get("tests") or {}
    change = bundle.get("change") or {}
    pub = bundle.get("publication") or {}
    comparisons = enrich_comparisons_from_api_load(bundle.get("comparisons") or {}, tests)

    rows_ep = []
    for ep in comparisons.get("endpoints") or []:
        p95 = (ep.get("latency_ms") or {}).get("p95") or {}
        rows_ep.append(
            f"<tr><td>{_esc(ep.get('service'))}</td><td>{_esc(ep.get('route'))}</td>"
            f"<td>{_esc(p95.get('b'))} → {_esc(p95.get('r'))}</td>"
            f"<td>{_esc(ep.get('delta_flags'))}</td></tr>"
        )
    rows_res = []
    for res in comparisons.get("resources") or []:
        cpu = (res.get("cpu") or {}).get("max_pct_limit") or {}
        mem = (res.get("memory") or {}).get("max_pct_limit") or {}
        rows_res.append(
            f"<tr><td>{_esc(res.get('deployment'))}</td>"
            f"<td>{_esc(cpu.get('b'))} → {_esc(cpu.get('r'))}</td>"
            f"<td>{_esc(mem.get('b'))} → {_esc(mem.get('r'))}</td>"
            f"<td>{_esc(res.get('oom_killed'))}</td>"
            f"<td>{_esc(res.get('restarts'))}</td></tr>"
        )

    users = comparisons.get("users") or {}
    users_html = (
        f"<p>active≈ {_esc(users.get('active_approx'))} · "
        f"auth_fail={_esc(users.get('auth_fail_rate'))} · "
        f"5xx={_esc(users.get('user_facing_5xx'))} · "
        f"source={_esc(users.get('source'))}</p>"
        if users
        else "<p><i>No user metrics</i></p>"
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Release Dossier {_esc(bundle.get('tracking_id'))}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#111;line-height:1.4}}
h1,h2{{color:#111}} table{{border-collapse:collapse;width:100%;margin:12px 0}}
td,th{{border:1px solid #D1D5DB;padding:6px 8px;text-align:left;font-size:13px}}
th{{background:#F3F4F6}}
.banner{{padding:10px;border:1px solid #D1D5DB;margin:12px 0}}
.warn{{background:#FFFBEB}} .fail{{background:#FEF2F2}} .ok{{background:#F0FDF4}}
.muted{{color:#6B7280;font-size:12px}}
</style></head><body>
<h1>Release dossier</h1>
<p>tracking_id={_esc(bundle.get('tracking_id'))} · gnx={_esc(bundle.get('gnx_mode'))} ·
generated={_esc(datetime.now(timezone.utc).isoformat())}</p>
<div class="banner {'ok' if verification.get('releasable') else 'fail'}">
<b>Recommendation:</b> {_esc((analysis.get('recommendation') or 'unknown').upper())} ·
feature_clean={_esc(verification.get('feature_clean'))} ·
infra_clean={_esc(verification.get('infra_clean'))}
</div>
<h2>1. Executive summary</h2>
<p>{_esc(analysis.get('executive_summary') or '—')}</p>
<h2>2. Change</h2>
{_change_summary(change)}
<h2>3. Tests</h2>
{_ui_summary(tests)}
<table>
<tr><th>Service</th><th>Scenario</th><th>Result</th><th>URL</th><th>p50 ms</th><th>p95 ms</th><th>Codes</th></tr>
{_rows_api_load(tests)}
</table>
<p class="muted">API load VUs from execute_matrix (direct HTTP against LoadContext base_urls).</p>
<h2>4. Endpoint comparison (baseline → run)</h2>
<table><tr><th>Service</th><th>Route</th><th>p95 ms</th><th>Flags</th></tr>
{''.join(rows_ep) or '<tr><td colspan="4">none</td></tr>'}
</table>
<h2>5. Infra comparison (CPU / RAM)</h2>
<table><tr><th>Deployment</th><th>CPU max%</th><th>RAM max%</th><th>OOM</th><th>Restarts</th></tr>
{''.join(rows_res) or '<tr><td colspan="5">none (Grafana observe not live)</td></tr>'}
</table>
<h2>6. Users</h2>
{users_html}
<h2>7. Verification</h2>
<p>releasable={_esc(verification.get('releasable'))} ·
feature_clean={_esc(verification.get('feature_clean'))} ·
infra_clean={_esc(verification.get('infra_clean'))}</p>
<pre>blockers={_esc(verification.get('blockers'))}
warnings={_esc(verification.get('warnings'))}</pre>
<h2>8. LLM / narrative</h2>
<p><b>Code:</b> {_esc(analysis.get('code_impact') or '—')}</p>
<p><b>Infra:</b> {_esc(analysis.get('infra_impact') or '—')}</p>
<p><b>Risks:</b> {_esc(analysis.get('risks') or '—')}</p>
<p><b>Feature:</b> {_esc(analysis.get('feature_narrative') or '—')}</p>
<h2>9. Appendix</h2>
<pre>unavailable={_esc(comparisons.get('unavailable'))}
publication={_esc(pub)}</pre>
</body></html>"""


def _write_pdf(html_body: str, pdf_path: Path) -> None:
    """Prefer weasyprint; fall back to xhtml2pdf (works on Windows without GTK)."""
    try:
        from weasyprint import HTML  # type: ignore

        HTML(string=html_body).write_pdf(str(pdf_path))
        return
    except Exception as weasy_exc:  # noqa: BLE001
        try:
            from io import BytesIO

            from xhtml2pdf import pisa  # type: ignore

            buf = BytesIO()
            result = pisa.CreatePDF(html_body, dest=buf, encoding="utf-8")
            if result.err:
                raise RuntimeError(f"xhtml2pdf errors={result.err}") from weasy_exc
            pdf_path.write_bytes(buf.getvalue())
            return
        except Exception as xhtml_exc:  # noqa: BLE001
            raise RuntimeError(
                f"weasyprint failed ({type(weasy_exc).__name__}: {weasy_exc}); "
                f"xhtml2pdf failed ({type(xhtml_exc).__name__}: {xhtml_exc})"
            ) from xhtml_exc


def publish_pdf_dossier(bundle: dict[str, Any], *, tracking_id: str) -> dict[str, Any]:
    """
    Always write HTML dossier. Prefer PDF via weasyprint, else xhtml2pdf.
    Install with: `pip install 'am-qa-agent[pdf]'`.
    """
    html_body = render_dossier_html(bundle)
    root = Path(os.getenv("QA_AGENT_ARTIFACT_DIR") or "artifacts/pdf")
    root.mkdir(parents=True, exist_ok=True)
    html_path = root / f"{tracking_id}-release-dossier.html"
    html_path.write_text(html_body, encoding="utf-8")

    pdf_path = root / f"{tracking_id}-release-dossier.pdf"
    pdf_written = False
    pdf_error: str | None = None
    if os.getenv("QA_AGENT_SKIP_PDF", "").lower() not in {"1", "true", "yes"}:
        try:
            _write_pdf(html_body, pdf_path)
            pdf_written = pdf_path.is_file() and pdf_path.stat().st_size > 0
            if not pdf_written:
                pdf_error = "pdf_file_empty"
        except Exception as exc:  # noqa: BLE001 — optional dep / native libs
            pdf_error = str(exc)

    local_ref = f"file://{(pdf_path if pdf_written else html_path).resolve()}"
    out: dict[str, Any] = {
        "pdf_docs_ref": local_ref,
        "html_path": str(html_path.resolve()),
        "pdf_path": str(pdf_path.resolve()) if pdf_written else None,
        "pdf_written": pdf_written,
        "format": "pdf" if pdf_written else "html",
        "local_path": str((pdf_path if pdf_written else html_path).resolve()),
        "content_type": "application/pdf" if pdf_written else "text/html",
    }
    if pdf_error:
        out["pdf_error"] = pdf_error[:800]
        out["note"] = "HTML dossier written; PDF engines failed (see pdf_error)"
    return out
