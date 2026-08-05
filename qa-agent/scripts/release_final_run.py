#!/usr/bin/env python3
"""Final soak run: wait N minutes, score tech/alerts/business, Sheet + Cliq."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QA_AGENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(QA_AGENT))
sys.path.insert(0, str(QA_AGENT / "release_gate"))
sys.path.insert(0, str(ROOT.parent / "am-infra" / "scripts"))

from intelligence.cliq_final import build_cliq_final_body, send_cliq_final  # noqa: E402
from intelligence.stability_score import (  # noqa: E402
    compute_stability,
    score_alerts,
    score_business,
    score_technical,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _find_pack(release_id: str | None) -> Path:
    base = Path(os.getenv("QA_AGENT_ARTIFACT_DIR") or (ROOT / "artifacts" / "releases"))
    if release_id:
        path = base / release_id
        if path.is_dir():
            return path
        raise FileNotFoundError(f"Pack not found: {path}")
    if not base.is_dir():
        raise FileNotFoundError(f"No releases under {base}; run release:report first")
    candidates = sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in candidates:
        if c.is_dir() and (c / "summary.json").is_file():
            return c
    raise FileNotFoundError("No summary.json packs found")


def _load_summary(pack: Path) -> dict[str, Any]:
    return json.loads((pack / "summary.json").read_text(encoding="utf-8"))


def _collect_fixture_or_live(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Collect pillars. Live Grafana/Alertmanager hooks TBD; fixtures for dry-run."""
    if args.fixtures:
        tech = score_technical(
            {"p95_ok": True, "cpu_ok": True, "mem_ok": True, "restart_ok": True, "error_ok": True}
        )
        alerts = score_alerts([])
        biz = score_business(
            [
                {"id": "login_success_rate", "ok": True, "weight": 1.0},
                {"id": "ui_5xx_rate", "ok": True, "weight": 1.0},
                {"id": "portfolio_api_error_rate", "ok": True, "weight": 1.0},
            ]
        )
        return tech, alerts, biz

    # Placeholder live path: mark unavailable until Grafana service_map is filled
    tech = score_technical({}, unavailable=True)
    alerts = score_alerts([], unavailable=os.getenv("QA_AGENT_SKIP_ALERTS", "").lower() in {"1", "true"})
    if alerts.get("mode") != "unavailable":
        # empty firing list = full alerts score when query succeeds with zero fires
        alerts = score_alerts([])
    try:
        from lib.asrax_release_sheet import load_business_slis

        slis_cfg = load_business_slis()
        # Without live PromQL results, treat as unavailable
        biz = score_business(
            [{"id": s.get("id"), "ok": False, "weight": s.get("weight", 1)} for s in slis_cfg],
            unavailable=True,
        )
    except Exception:
        biz = score_business([], unavailable=True)
    return tech, alerts, biz


def _upload_drive(pack: Path, release_id: str) -> dict[str, str]:
    links: dict[str, str] = {}
    if os.getenv("QA_AGENT_SKIP_DRIVE", "").lower() in {"1", "true", "yes"}:
        return links
    try:
        from lib import asrax_release_sheet as sheet

        creds = sheet.google_creds()
        drive = sheet.drive_client(creds)
        asrax = sheet.ensure_drive_folder(drive, "Asrax")
        releases = sheet.ensure_drive_folder(drive, "Releases", asrax)
        folder = sheet.ensure_drive_folder(drive, release_id, releases)
        for key, name in (
            ("master_pdf", "master-release-report.pdf"),
            ("final_pdf", "final-analysis.pdf"),
            ("dossier_pdf", "release-dossier.pdf"),
            ("ui_summary", "summary.json"),
        ):
            path = pack / name if key != "final_pdf" else pack / "final" / name
            if key == "ui_summary":
                path = pack / "summary.json"
            if not path.is_file():
                continue
            mime = "application/pdf" if path.suffix == ".pdf" else "application/json"
            meta = sheet.upload_file_to_drive(drive, local_path=path, folder_id=folder, mime_type=mime)
            links[key] = meta.get("webViewLink") or ""
    except Exception as exc:  # noqa: BLE001
        links["error"] = str(exc)
    return links


def _publish_stability(sheet_id: str, summary: dict[str, Any], stability: dict[str, Any], links: dict[str, str]) -> dict[str, Any]:
    try:
        from lib import asrax_release_sheet as sheet

        sheets = sheet.sheets_client()
        sheet.append_stability_row(
            sheets,
            sheet_id,
            [
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                stability.get("release_id"),
                stability.get("soak_minutes"),
                (stability.get("pillars") or {}).get("technical", {}).get("score"),
                (stability.get("pillars") or {}).get("alerts", {}).get("score"),
                (stability.get("pillars") or {}).get("business", {}).get("score"),
                stability.get("stability_score"),
                stability.get("band"),
                stability.get("system_stable"),
                links.get("final_pdf", ""),
                summary.get("cliq", {}).get("ok") or summary.get("cliq", {}).get("skipped"),
                "final soak",
            ],
        )
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _write_final_html(pack: Path, stability: dict[str, Any], body: str) -> Path:
    path = pack / "final" / "final-analysis.html"
    path.write_text(
        f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Final {stability.get('release_id')}</title></head>
<body><h1>Final stability — {stability.get('band')} ({stability.get('stability_score')})</h1>
<pre>{json.dumps(stability, indent=2)}</pre>
<h2>Cliq message</h2><pre>{body}</pre></body></html>""",
        encoding="utf-8",
    )
    return path


async def main_async(args: argparse.Namespace) -> int:
    pack = _find_pack(args.release_id)
    summary = _load_summary(pack)
    release_id = summary.get("release_id") or pack.name

    if args.soak_min > 0 and not args.notify_only:
        print(f"Soaking {args.soak_min} minutes for {release_id}...", flush=True)
        time.sleep(args.soak_min * 60)

    end = _utc_now()
    start = end - timedelta(minutes=max(args.soak_min, 1))
    window = {"start": start.isoformat(), "end": end.isoformat()}

    tech, alerts, biz = _collect_fixture_or_live(args)
    stability = compute_stability(
        technical=tech,
        alerts=alerts,
        business=biz,
        soak_minutes=args.soak_min,
        release_id=release_id,
        window=window,
        allow_unavailable_stable=args.allow_unavailable_stable,
    )
    (pack / "final" / "stability-score.json").write_text(
        json.dumps(stability, indent=2), encoding="utf-8"
    )
    (pack / "final" / "soak-metrics.json").write_text(
        json.dumps({"technical": tech}, indent=2), encoding="utf-8"
    )
    (pack / "final" / "alerts.json").write_text(
        json.dumps({"alerts": alerts}, indent=2), encoding="utf-8"
    )
    (pack / "final" / "business.json").write_text(
        json.dumps({"business": biz}, indent=2), encoding="utf-8"
    )

    ui = summary.get("ui") or {}
    sheet_url = os.getenv("ASRAX_RELEASE_SHEET_URL") or (
        f"https://docs.google.com/spreadsheets/d/"
        f"{os.getenv('ASRAX_RELEASE_SHEET_ID', '1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc')}"
    )
    drive_links = {} if args.skip_drive else _upload_drive(pack, release_id)
    body = build_cliq_final_body(
        release_name=args.release_name or release_id,
        stability=stability,
        ui_decision=str(ui.get("decision") or ""),
        ui_hard_fails=int(ui.get("hard_fail_count") or 0),
        sheet_url=sheet_url,
        drive_links=drive_links,
        grafana_url=os.getenv("ASRAX_GRAFANA_SOAK_URL", ""),
        owner=os.getenv("ASRAX_RELEASE_OWNER", ""),
    )
    (pack / "final" / "cliq-message.md").write_text(body, encoding="utf-8")
    html = _write_final_html(pack, stability, body)
    try:
        from xhtml2pdf import pisa

        pdf = pack / "final" / "final-analysis.pdf"
        with html.open("rb") as src, pdf.open("wb") as dst:
            pisa.CreatePDF(src, dest=dst)
    except Exception:
        pass

    cliq_result: dict[str, Any] = {"skipped": True}
    if not args.skip_cliq:
        cliq_result = await send_cliq_final(
            title=f"Asrax FINAL {stability.get('band')} — {release_id}",
            body=body,
        )
    summary["stability"] = stability
    summary["cliq"] = cliq_result
    summary["drive_links"] = drive_links
    summary["phase"] = "FINAL"

    sheet_id = os.getenv("ASRAX_RELEASE_SHEET_ID") or "1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc"
    if not args.skip_sheet:
        summary["stability_sheet"] = _publish_stability(sheet_id, summary, stability, drive_links)

    (pack / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"release_id": release_id, "band": stability.get("band"), "score": stability.get("stability_score"), "cliq": cliq_result}, indent=2))
    return 0 if stability.get("system_stable") else 2


def main() -> int:
    p = argparse.ArgumentParser(description="Asrax final soak + Cliq summary")
    p.add_argument("--release-id", default=None)
    p.add_argument("--release-name", default="Release 01")
    p.add_argument("--env", default="prod")
    p.add_argument("--soak-min", type=int, default=30)
    p.add_argument("--fixtures", action="store_true", help="Use canned metrics (CI/lab)")
    p.add_argument("--allow-unavailable-stable", action="store_true")
    p.add_argument("--skip-cliq", action="store_true")
    p.add_argument("--skip-sheet", action="store_true")
    p.add_argument("--skip-drive", action="store_true")
    p.add_argument("--notify-only", action="store_true", help="Skip soak sleep; rebuild notify from pack")
    args = p.parse_args()
    if args.notify_only:
        args.soak_min = 0
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
