"""Release-ops activities — T0 pack, soak score, Sheet/Drive/Cliq publish (qa-agent).

Ledger step names match Temporal UI activity names for easy debug:
  release_ops_init → release_ops_ui_suite → release_ops_pack_t0
  → release_ops_stability_score → release_ops_publish_sheet
  → release_ops_publish_drive → release_ops_cliq_final → release_ops_complete
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from temporalio import activity

from stores import get_ledger


def _repo_root() -> Path:
    # .../qa-agent/release_gate/orchestrator/activities/release_ops.py → am-qa-agents
    return Path(__file__).resolve().parents[4]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: str | None) -> datetime:
    raw = (value or "").strip()
    if not raw:
        return datetime.now(timezone.utc)
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%MZ")


def _day(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _year(dt: datetime) -> str:
    return dt.strftime("%Y")


def _pack_dir(*, release_id: str, triggered_at: datetime) -> Path:
    # qa-agent local tree (not am-infra Asrax/Releases Drive layout)
    base = Path(
        os.getenv("QA_AGENT_ARTIFACT_DIR")
        or (_repo_root() / "artifacts" / "asrax-release-ops")
    )
    path = base / _day(triggered_at) / release_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "ui").mkdir(exist_ok=True)
    (path / "final").mkdir(exist_ok=True)
    return path


def _dated_drive_name(
    *,
    release_id: str,
    triggered_stamp: str,
    workflow_stamp: str,
    stem: str,
    suffix: str,
) -> str:
    return (
        f"{release_id}_triggered-{triggered_stamp}_workflow-{workflow_stamp}_{stem}{suffix}"
    )


@activity.defn(name="activity_release_ops_init")
async def activity_release_ops_init(payload: dict[str, Any]) -> dict[str, Any]:
    """Allocate release_id + pack path; write skeleton summary.json."""
    tracking_id = str(payload.get("tracking_id") or f"qa-{uuid.uuid4().hex[:12]}")
    triggered_at = _parse_utc(
        str(payload.get("triggered_at") or payload.get("request_at") or "") or None
    )
    workflow_started_at = _parse_utc(
        str(payload.get("workflow_started_at") or "") or None
    )
    release_id = str(
        payload.get("release_id")
        or (
            f"asrax-r01-{triggered_at.strftime('%Y%m%d')}-"
            f"{uuid.uuid4().hex[:8]}"
        )
    )
    pack = _pack_dir(release_id=release_id, triggered_at=triggered_at)
    summary = {
        "tracking_id": tracking_id,
        "release_id": release_id,
        "created_at": _utc(),
        "triggered_at": triggered_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workflow_started_at": workflow_started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "triggered_stamp": _stamp(triggered_at),
        "workflow_stamp": _stamp(workflow_started_at),
        "env": payload.get("env") or "prod",
        "target_url": payload.get("target_url") or "https://am.asrax.in",
        "suite": payload.get("suite") or "prod_ui_full",
        "pack_path": str(pack),
        "phase": "INIT",
        "workflow": "AsraxReleaseOpsWorkflow",
        "drive_root": "minio://qa-agent/asrax-release-ops",
        "artifact_store": "minio",
    }
    (pack / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    workflow_id = str(payload.get("workflow_id") or f"asrax-release-ops-{release_id}")
    get_ledger().create_run(
        tracking_id=tracking_id,
        workflow_id=workflow_id,
        meta={"release_id": release_id, "workflow": "AsraxReleaseOpsWorkflow"},
    )
    out = {
        "tracking_id": tracking_id,
        "release_id": release_id,
        "pack_path": str(pack),
        "workflow_id": workflow_id,
        "summary": summary,
        "status": "INITIALIZED",
    }
    get_ledger().upsert_step(tracking_id, "release_ops_init", out)
    activity.logger.info(
        "release_ops.init release_id=%s pack=%s",
        release_id,
        pack,
    )
    return out


@activity.defn(name="activity_release_ops_ui_suite")
async def activity_release_ops_ui_suite(payload: dict[str, Any]) -> dict[str, Any]:
    """Run UI suite (or skip) and attach results to pack."""
    tracking_id = str(payload["tracking_id"])
    release_id = str(payload["release_id"])
    pack = Path(str(payload["pack_path"]))
    skip = bool(payload.get("skip_ui"))
    suite = str(payload.get("suite") or "prod_ui_full")
    url = str(payload.get("target_url") or "https://am.asrax.in")
    login_mode = str(payload.get("login_mode") or "credentials")

    if skip:
        ui = {
            "suite": suite,
            "decision": "SKIPPED",
            "results": [],
            "hard_fail_count": 0,
            "soft_fail_count": 0,
            "mode": "skipped",
        }
        get_ledger().upsert_step(tracking_id, "release_ops_ui_suite", ui)
        return ui

    # Import CLI helpers lazily (Playwright-heavy)
    import sys

    qa_agent = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(qa_agent))
    sys.path.insert(0, str(qa_agent / "ui_evidence"))

    from types import SimpleNamespace

    from scripts.release_report import _run_ui_suite  # type: ignore

    ui = await _run_ui_suite(
        SimpleNamespace(
            suite=suite,
            url=url,
            portfolio_id=payload.get("portfolio_id"),
            login_mode=login_mode,
        )
    )
    src = ui.get("suite_summary_path")
    if src and Path(str(src)).is_file():
        dest = pack / "ui" / Path(str(src)).name
        dest.write_bytes(Path(str(src)).read_bytes())
        ui["suite_summary_path"] = str(dest)

    summary_path = pack / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    summary["ui"] = ui
    summary["phase"] = "UI_DONE"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    get_ledger().upsert_step(tracking_id, "release_ops_ui_suite", ui)
    activity.logger.info(
        "release_ops.ui_suite decision=%s hard=%s",
        ui.get("decision"),
        ui.get("hard_fail_count"),
    )
    return ui


@activity.defn(name="activity_release_ops_pack_t0")
async def activity_release_ops_pack_t0(payload: dict[str, Any]) -> dict[str, Any]:
    """Write master HTML/PDF + optional Sheet QA Evidence row (T0)."""
    tracking_id = str(payload["tracking_id"])
    pack = Path(str(payload["pack_path"]))
    summary_path = pack / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    html = pack / "master-release-report.html"
    ui = summary.get("ui") or {}
    rows = "".join(
        f"<tr><td>{r.get('profile')}</td><td>{r.get('status')}</td></tr>"
        for r in ui.get("results") or []
    )
    html.write_text(
        f"<html><body><h1>{summary.get('release_id')}</h1>"
        f"<p>decision={ui.get('decision')}</p><table>{rows}</table></body></html>",
        encoding="utf-8",
    )
    try:
        from xhtml2pdf import pisa

        with html.open("rb") as src, (pack / "master-release-report.pdf").open("wb") as dst:
            pisa.CreatePDF(src, dest=dst)
        summary["master_pdf"] = str(pack / "master-release-report.pdf")
    except Exception as exc:  # noqa: BLE001
        summary["master_pdf_error"] = str(exc)

    sheet_out: dict[str, Any] = {"skipped": True}
    if not payload.get("skip_sheet"):
        try:
            import sys

            sys.path.insert(0, str(_repo_root().parent / "am-infra" / "scripts"))
            from lib import asrax_release_sheet as sheet

            sheet_id = str(
                payload.get("sheet_id")
                or os.getenv("ASRAX_RELEASE_SHEET_ID")
                or "1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc"
            )
            sheets = sheet.sheets_client()
            sheet.sync_namespace_and_risk_tabs(sheets, sheet_id)
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
                    "",
                    summary.get("master_pdf") or "",
                    str(pack),
                    "Temporal T0",
                ],
            )
            sheet_out = {"ok": True, "sheet_id": sheet_id}
        except Exception as exc:  # noqa: BLE001
            sheet_out = {"ok": False, "error": str(exc)}

    summary["sheet_t0"] = sheet_out
    summary["phase"] = "T0"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    out = {"pack_path": str(pack), "sheet": sheet_out, "status": "T0_PACKED"}
    get_ledger().upsert_step(tracking_id, "release_ops_pack_t0", out)
    return out


@activity.defn(name="activity_release_ops_stability_score")
async def activity_release_ops_stability_score(payload: dict[str, Any]) -> dict[str, Any]:
    """Compute stability score after soak (fixtures or live placeholders)."""
    tracking_id = str(payload["tracking_id"])
    pack = Path(str(payload["pack_path"]))
    soak_min = int(payload.get("soak_min") or 30)
    use_fixtures = bool(payload.get("fixtures"))

    from intelligence.stability_score import (
        compute_stability,
        score_alerts,
        score_business,
        score_technical,
    )

    if use_fixtures:
        tech = score_technical(
            {
                "p95_ok": True,
                "cpu_ok": True,
                "mem_ok": True,
                "restart_ok": True,
                "error_ok": True,
            }
        )
        alerts = score_alerts([])
        biz = score_business([{"id": "login_success_rate", "ok": True, "weight": 1}])
    else:
        tech = score_technical({}, unavailable=True)
        alerts = score_alerts([])
        biz = score_business([], unavailable=True)

    stability = compute_stability(
        technical=tech,
        alerts=alerts,
        business=biz,
        soak_minutes=soak_min,
        release_id=str(payload.get("release_id") or ""),
        allow_unavailable_stable=bool(payload.get("allow_unavailable_stable")),
    )
    final = pack / "final"
    final.mkdir(exist_ok=True)
    (final / "stability-score.json").write_text(json.dumps(stability, indent=2), encoding="utf-8")

    summary_path = pack / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    summary["stability"] = stability
    summary["phase"] = "SCORED"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    get_ledger().upsert_step(tracking_id, "release_ops_stability_score", stability)
    activity.logger.info(
        "release_ops.score band=%s score=%s",
        stability.get("band"),
        stability.get("stability_score"),
    )
    return stability


@activity.defn(name="activity_release_ops_publish_sheet")
async def activity_release_ops_publish_sheet(payload: dict[str, Any]) -> dict[str, Any]:
    """Append Stability tab row."""
    tracking_id = str(payload["tracking_id"])
    if payload.get("skip_sheet"):
        out = {"skipped": True}
        get_ledger().upsert_step(tracking_id, "release_ops_publish_sheet", out)
        return out

    stability = payload.get("stability") or {}
    try:
        import sys

        sys.path.insert(0, str(_repo_root().parent / "am-infra" / "scripts"))
        from lib import asrax_release_sheet as sheet

        sheet_id = str(
            payload.get("sheet_id")
            or os.getenv("ASRAX_RELEASE_SHEET_ID")
            or "1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc"
        )
        sheets = sheet.sheets_client()
        sheet.append_stability_row(
            sheets,
            sheet_id,
            [
                _utc(),
                stability.get("release_id"),
                stability.get("soak_minutes"),
                (stability.get("pillars") or {}).get("technical", {}).get("score"),
                (stability.get("pillars") or {}).get("alerts", {}).get("score"),
                (stability.get("pillars") or {}).get("business", {}).get("score"),
                stability.get("stability_score"),
                stability.get("band"),
                stability.get("system_stable"),
                "",
                "",
                "Temporal final",
            ],
        )
        out = {"ok": True, "sheet_id": sheet_id}
    except Exception as exc:  # noqa: BLE001
        out = {"ok": False, "error": str(exc)}
    get_ledger().upsert_step(tracking_id, "release_ops_publish_sheet", out)
    return out


@activity.defn(name="activity_release_ops_publish_drive")
async def activity_release_ops_publish_drive(payload: dict[str, Any]) -> dict[str, Any]:
    """Upload pack to MinIO (canonical) + Google Drive under QA-Agent path (not Asrax/Releases)."""
    tracking_id = str(payload["tracking_id"])
    if payload.get("skip_drive") and payload.get("skip_minio"):
        out = {"skipped": True, "links": {}, "store": "none"}
        get_ledger().upsert_step(tracking_id, "release_ops_publish_drive", out)
        return out

    pack = Path(str(payload["pack_path"]))
    release_id = str(payload["release_id"])
    summary_path = pack / "summary.json"
    summary: dict[str, Any] = {}
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    triggered_at = _parse_utc(str(summary.get("triggered_at") or payload.get("triggered_at") or ""))
    workflow_started_at = _parse_utc(
        str(summary.get("workflow_started_at") or payload.get("workflow_started_at") or "")
    )
    links: dict[str, str] = {}
    errors: list[str] = []
    stores: list[str] = []

    if not payload.get("skip_minio"):
        try:
            from adapters.minio_store import upload_release_pack

            minio_out = upload_release_pack(
                pack=pack,
                release_id=release_id,
                triggered_at=triggered_at,
                workflow_started_at=workflow_started_at,
            )
            links.update(minio_out.get("links") or {})
            if minio_out.get("ok"):
                stores.append("minio")
            else:
                errors.extend(minio_out.get("errors") or [str(minio_out.get("error") or "minio_failed")])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"minio:{exc}")

    if not payload.get("skip_drive"):
        try:
            import sys

            from adapters.minio_store import dated_object_name, mime_for

            sys.path.insert(0, str(_repo_root().parent / "am-infra" / "scripts"))
            from lib import asrax_release_sheet as sheet

            trig = _stamp(triggered_at)
            wf = _stamp(workflow_started_at)
            drive = sheet.drive_client()
            root = sheet.ensure_drive_folder(drive, "QA-Agent")
            ops = sheet.ensure_drive_folder(drive, "Asrax-Release-Ops", root)
            year_f = sheet.ensure_drive_folder(drive, _year(triggered_at), ops)
            day_f = sheet.ensure_drive_folder(drive, _day(triggered_at), year_f)
            folder = sheet.ensure_drive_folder(drive, release_id, day_f)
            links["drive_folder"] = f"https://drive.google.com/drive/folders/{folder}"
            if not links.get("folder"):
                links["folder"] = links["drive_folder"]

            uploads: list[tuple[str, str, str]] = [
                ("drive_master_pdf", "master-release-report.pdf", "master-release-report"),
                ("drive_summary", "summary.json", "summary"),
                ("drive_stability", "final/stability-score.json", "stability-score"),
            ]
            ui_dir = pack / "ui"
            if ui_dir.is_dir():
                for path in sorted(ui_dir.rglob("*.png"))[:20]:
                    rel = path.relative_to(pack).as_posix()
                    uploads.append((f"drive_shot_{path.stem}"[:80], rel, f"shot-{path.stem}"[:60]))

            for key_name, rel, stem in uploads:
                path = pack / rel
                if not path.is_file():
                    continue
                name = dated_object_name(
                    release_id=release_id,
                    triggered_stamp=trig,
                    workflow_stamp=wf,
                    stem=stem,
                    suffix=path.suffix,
                )
                meta = sheet.upload_file_to_drive(
                    drive,
                    local_path=path,
                    folder_id=folder,
                    mime_type=mime_for(path),
                    name=name,
                )
                url = meta.get("webViewLink") or ""
                links[key_name] = url
                if key_name == "drive_master_pdf" and not links.get("master_pdf"):
                    links["master_pdf"] = url
                    links["final_pdf"] = url
            stores.append("drive")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"drive:{exc}")

    out = {
        "ok": bool(stores) and not errors,
        "store": "+".join(stores) if stores else "none",
        "links": links,
        "errors": errors,
    }
    if stores and errors:
        out["ok"] = True
        out["partial"] = True
    get_ledger().upsert_step(tracking_id, "release_ops_publish_drive", out)
    return out


@activity.defn(name="activity_release_ops_cliq_final")
async def activity_release_ops_cliq_final(payload: dict[str, Any]) -> dict[str, Any]:
    """Post one Cliq final card for everyone."""
    tracking_id = str(payload["tracking_id"])
    pack = Path(str(payload["pack_path"]))
    stability = payload.get("stability") or {}
    links = (payload.get("drive") or {}).get("links") or {}
    ui = payload.get("ui") or {}

    from intelligence.cliq_final import build_cliq_final_body, send_cliq_final

    sheet_url = os.getenv("ASRAX_RELEASE_SHEET_URL") or (
        f"https://docs.google.com/spreadsheets/d/"
        f"{os.getenv('ASRAX_RELEASE_SHEET_ID', '1Ruzmdj7oZJloIkG7ImIX2595v_H6RLOvIc-sCo9jHIc')}"
    )
    body = build_cliq_final_body(
        release_name=str(payload.get("release_name") or stability.get("release_id") or ""),
        stability=stability,
        ui_decision=str(ui.get("decision") or ""),
        ui_hard_fails=int(ui.get("hard_fail_count") or 0),
        sheet_url=sheet_url,
        drive_links=links,
        grafana_url=os.getenv("ASRAX_GRAFANA_SOAK_URL", ""),
        owner=os.getenv("ASRAX_RELEASE_OWNER", ""),
    )
    (pack / "final" / "cliq-message.md").write_text(body, encoding="utf-8")

    if payload.get("skip_cliq"):
        out = {"skipped": True, "body": body}
    else:
        out = await send_cliq_final(
            title=f"Asrax FINAL {stability.get('band')} — {stability.get('release_id')}",
            body=body,
        )
        out["body"] = body

    summary_path = pack / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["cliq"] = {k: v for k, v in out.items() if k != "body"}
        summary["drive_links"] = links
        summary["minio_links"] = links
        summary["phase"] = "FINAL"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    get_ledger().upsert_step(tracking_id, "release_ops_cliq_final", {k: v for k, v in out.items() if k != "body"})
    return out


@activity.defn(name="activity_release_ops_complete")
async def activity_release_ops_complete(payload: dict[str, Any]) -> dict[str, Any]:
    """Final ledger marker for Temporal UI."""
    tracking_id = str(payload["tracking_id"])
    stability = payload.get("stability") or {}
    out = {
        "status": "COMPLETED",
        "release_id": payload.get("release_id"),
        "band": stability.get("band"),
        "system_stable": stability.get("system_stable"),
        "pack_path": payload.get("pack_path"),
        "completed_at": _utc(),
    }
    get_ledger().upsert_step(tracking_id, "release_ops_complete", out)
    return out
