#!/usr/bin/env python3
"""T0 release report: run UI suite, build pack + summary, optional Sheet publish."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]  # am-qa-agents
QA_AGENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(QA_AGENT))
sys.path.insert(0, str(QA_AGENT / "ui_evidence"))
sys.path.insert(0, str(ROOT.parent / "am-infra" / "scripts"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _release_id(explicit: str | None) -> str:
    if explicit:
        return explicit
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"asrax-r01-{stamp}-{uuid.uuid4().hex[:8]}"


def _pack_dir(release_id: str) -> Path:
    base = Path(os.getenv("QA_AGENT_ARTIFACT_DIR") or (ROOT / "artifacts" / "releases"))
    path = base / release_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "ui").mkdir(exist_ok=True)
    (path / "final").mkdir(exist_ok=True)
    return path


def _write_master_html(pack: Path, summary: dict[str, Any]) -> Path:
    html = pack / "master-release-report.html"
    rows = "".join(
        f"<tr><td>{r.get('profile')}</td><td>{r.get('status')}</td>"
        f"<td>{r.get('soft_failures', 0)}</td></tr>"
        for r in (summary.get("ui") or {}).get("results") or []
    )
    html.write_text(
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{summary.get('release_id')} release report</title></head>
<body>
<h1>Asrax release report — {summary.get('release_id')}</h1>
<p>Generated: {summary.get('created_at')} | env: {summary.get('env')} | UI decision: {(summary.get('ui') or {}).get('decision')}</p>
<h2>UI suite</h2>
<table border="1" cellpadding="4"><tr><th>Profile</th><th>Status</th><th>Soft fails</th></tr>{rows}</table>
<p>Pack path: {pack}</p>
<p>See also release-dossier and ui/ artifacts. Final soak: npm run release:final</p>
</body></html>
""",
        encoding="utf-8",
    )
    return html


def _try_pdf_from_html(html_path: Path) -> Path | None:
    pdf_path = html_path.with_suffix(".pdf")
    try:
        from xhtml2pdf import pisa

        with html_path.open("rb") as src, pdf_path.open("wb") as dst:
            status = pisa.CreatePDF(src, dest=dst)
        if not status.err:
            return pdf_path
    except Exception:
        pass
    return None


async def _run_ui_suite(args: argparse.Namespace) -> dict[str, Any]:
    from ui_evidence.profiles.registry import suite_profiles

    # Prefer in-process suite runner
    ui_scripts = QA_AGENT / "ui_evidence"
    sys.path.insert(0, str(ui_scripts))
    from scripts import run_suite as suite_mod

    class _Args:
        suite = args.suite
        url = args.url
        target_file = None
        target = None
        env_file = None
        portfolio_id = args.portfolio_id
        login_mode = args.login_mode
        design_review = False
        tracking_id = getattr(args, "tracking_id", None)
        workflow_id = getattr(args, "workflow_id", None)
        release_id = getattr(args, "release_id", None)
        env = getattr(args, "env", None) or "prod"
        requested_by = getattr(args, "requested_by", None) or "asrax-release-ops"

    code, summary = await suite_mod.main_async(_Args())
    payload: dict[str, Any] = {
        "exit_code": code,
        "results": [],
        "decision": "UNKNOWN",
        **(summary or {}),
    }
    if summary.get("report_json"):
        payload["suite_summary_path"] = summary["report_json"]
    else:
        try:
            from ui_evidence.config import settings

            report_dir = Path(settings.REPORT_DIR)
        except Exception:
            report_dir = Path(os.getenv("TEMP") or "/tmp") / "am-ui-test-reports"
        suites = sorted(
            report_dir.glob("suite-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if suites:
            payload.update(json.loads(suites[0].read_text(encoding="utf-8")))
            payload["suite_summary_path"] = str(suites[0])
    payload["profiles"] = list(suite_profiles(args.suite))
    return payload


def _publish_sheet(summary: dict[str, Any], pack: Path) -> dict[str, Any]:
    sheet_id = (
        os.getenv("ASRAX_RELEASE_SHEET_ID")
        or "1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc"
    )
    try:
        from lib import asrax_release_sheet as sheet

        sheets = sheet.sheets_client()
        sheet.sync_namespace_and_risk_tabs(sheets, sheet_id)
        ui = summary.get("ui") or {}
        sheet.append_qa_evidence_row(
            sheets,
            sheet_id,
            [
                summary.get("created_at"),
                summary.get("release_id"),
                summary.get("env"),
                ui.get("suite") or summary.get("suite"),
                ui.get("decision"),
                ui.get("hard_fail_count"),
                ui.get("soft_fail_count"),
                summary.get("dossier_url") or "",
                summary.get("master_pdf_url") or str(pack / "master-release-report.pdf"),
                str(pack),
                "T0 release:report",
            ],
        )
        return {"ok": True, "sheet_id": sheet_id}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "sheet_id": sheet_id}


async def main_async(args: argparse.Namespace) -> int:
    release_id = _release_id(args.release_id)
    pack = _pack_dir(release_id)
    created = _utc_now()
    ui_payload: dict[str, Any] = {
        "suite": args.suite,
        "decision": "SKIPPED",
        "results": [],
        "hard_fail_count": 0,
        "soft_fail_count": 0,
    }

    if not args.skip_ui:
        print(f"Running UI suite {args.suite} → {args.url}", flush=True)
        ui_payload = await _run_ui_suite(args)
        # copy suite summary into pack
        src = ui_payload.get("suite_summary_path")
        if src and Path(src).is_file():
            dest = pack / "ui" / Path(src).name
            shutil.copy2(src, dest)
            ui_payload["suite_summary_path"] = str(dest)

    summary: dict[str, Any] = {
        "release_id": release_id,
        "created_at": created,
        "env": args.env,
        "target_url": args.url,
        "suite": args.suite,
        "ui": ui_payload,
        "pack_path": str(pack),
        "phase": "T0",
    }
    summary_path = pack / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    html = _write_master_html(pack, summary)
    pdf = _try_pdf_from_html(html)
    if pdf:
        summary["master_pdf"] = str(pdf)
    # placeholder dossier note
    dossier_note = pack / "release-dossier.PENDING.txt"
    dossier_note.write_text(
        "Attach Temporal dossier PDF here or re-run with worker available.\n",
        encoding="utf-8",
    )

    sheet_result = {"skipped": True}
    if not args.skip_sheet:
        sheet_result = _publish_sheet(summary, pack)
    summary["sheet"] = sheet_result
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps({"release_id": release_id, "pack": str(pack), "ui": ui_payload.get("decision"), "sheet": sheet_result}, indent=2))
    hard = int(ui_payload.get("hard_fail_count") or 0)
    if hard:
        return 1
    if ui_payload.get("decision") == "NO_GO":
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Asrax T0 release report")
    p.add_argument("--env", default=os.getenv("QA_AGENT_ENV") or "prod")
    p.add_argument("--url", default=os.getenv("MODERN_UI_URL") or "https://am.asrax.in")
    p.add_argument(
        "--suite",
        default="prod_ui_full",
        choices=["smoke", "release_gate", "prod_ui_full", "auth_user_module"],
    )
    p.add_argument("--login-mode", default="credentials", choices=["demo", "credentials"])
    p.add_argument("--portfolio-id", default=os.getenv("TEST_PORTFOLIO_ID"))
    p.add_argument("--release-id", default=None)
    p.add_argument("--skip-ui", action="store_true")
    p.add_argument("--skip-sheet", action="store_true")
    args = p.parse_args()
    if args.env == "prod" and args.login_mode == "demo":
        args.login_mode = "credentials"
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
