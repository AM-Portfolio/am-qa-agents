import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ui_evidence.config import settings
from ui_evidence.profiles.registry import (
    DETERMINISTIC_PROFILES,
    PROD_UI_FULL_PROFILES,
    RELEASE_GATE_PROFILES,
    SUITE_PROFILES,
    is_deterministic_profile,
    suite_profiles,
)
from ui_evidence.runner import execute_ui_test

logger = logging.getLogger(__name__)

router = APIRouter()

test_runs: Dict[str, Dict[str, Any]] = {}
_run_lock = asyncio.Lock()


class TestRunRequest(BaseModel):
    targetUrl: str = Field(..., description="Staging/Preprod application base URL")
    specification: Optional[str] = Field(default=None, description="Gherkin specs for target assertions")
    profile: str = Field(default="RELEASE_GATE", description="Run profile")
    commitSha: Optional[str] = Field(default=None)
    branch: Optional[str] = Field(default="main")
    callbackUrl: Optional[str] = Field(default=None)
    baselineMode: Optional[str] = Field(default=None)
    portfolioId: Optional[str] = Field(default=None)
    loginMode: Optional[str] = Field(default=None)
    persona: Optional[str] = Field(default=None)
    designReviewEnabled: Optional[bool] = Field(default=None)
    selfHealEnabled: Optional[bool] = Field(default=None)
    viewportWidth: Optional[int] = Field(default=None)
    viewportHeight: Optional[int] = Field(default=None)


class AuthTestRunRequest(BaseModel):
    targetUrl: Optional[str] = Field(default=None)
    uiMode: Optional[str] = Field(default=None, description="portfolio | main")
    commitSha: Optional[str] = Field(default=None)
    branch: Optional[str] = Field(default="main")
    baselineMode: Optional[str] = Field(default=None)


class ProfileTestRunRequest(BaseModel):
    profile: str = Field(..., description="Deterministic profile id")
    targetUrl: Optional[str] = Field(default=None)
    portfolioId: Optional[str] = Field(default=None)
    loginMode: Optional[str] = Field(default=None)
    persona: Optional[str] = Field(default=None)
    commitSha: Optional[str] = Field(default=None)
    branch: Optional[str] = Field(default="main")
    baselineMode: Optional[str] = Field(default=None)
    designReviewEnabled: Optional[bool] = Field(default=None)
    selfHealEnabled: Optional[bool] = Field(default=None)
    viewportWidth: Optional[int] = Field(default=None)
    viewportHeight: Optional[int] = Field(default=None)


class SuiteTestRunRequest(BaseModel):
    suite: str = Field(default="release_gate", description="smoke | release_gate | prod_ui_full")
    targetUrl: Optional[str] = Field(default=None)
    environment: Optional[str] = Field(default=None)
    portfolioId: Optional[str] = Field(default=None)
    loginMode: Optional[str] = Field(default="demo")
    commitSha: Optional[str] = Field(default=None)
    branch: Optional[str] = Field(default="main")
    designReviewEnabled: bool = Field(default=True)
    profiles: Optional[List[str]] = Field(default=None)


class TestRunResponse(BaseModel):
    testId: str
    status: str
    message: str


async def execute_agent_task(test_id: str, payload: Dict[str, Any]) -> None:
    async with _run_lock:
        await _execute_agent_task_inner(test_id, payload)


async def _execute_agent_task_inner(test_id: str, payload: Dict[str, Any]) -> None:
    logger.info(
        "Starting UI test run %s profile=%s target=%s",
        test_id,
        payload.get("profile"),
        payload.get("targetUrl"),
    )
    test_runs[test_id]["status"] = "RUNNING"

    if payload.get("suite"):
        result = await _execute_suite(test_id, payload)
    else:
        result = await execute_ui_test(test_id, payload)
    test_runs[test_id].update(result)

    if result.get("status") in ("COMPLETED", "GO", "GO_WITH_CAVEATS"):
        callback_url = payload.get("callbackUrl")
        if callback_url:
            await trigger_vcs_callback(
                callback_url,
                "success",
                f"UI Tests completed. Report: {result.get('report')}",
            )
        return

    callback_url = payload.get("callbackUrl")
    if callback_url:
        await trigger_vcs_callback(
            callback_url,
            "failure",
            f"UI Tests failed: {result.get('error')}",
        )


async def _execute_suite(suite_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run suite profiles sequentially (login each run for isolation via API)."""
    suite_name = payload.get("suite") or "release_gate"
    try:
        default_profiles = list(suite_profiles(suite_name))
    except ValueError:
        default_profiles = list(RELEASE_GATE_PROFILES)
    profiles = payload.get("profiles") or default_profiles
    target = payload.get("targetUrl") or settings.MODERN_UI_MAIN_URL
    login_mode = payload.get("loginMode") or "demo"
    if suite_name == "prod_ui_full" and login_mode == "demo":
        login_mode = "credentials"
    results: list[dict[str, Any]] = []
    hard_fail = 0
    soft_fail = 0
    for profile in profiles:
        child_id = f"{suite_id[:8]}-{profile.lower()[:12]}"
        child_payload = {
            "targetUrl": target,
            "specification": "",
            "profile": profile,
            "commitSha": payload.get("commitSha"),
            "branch": payload.get("branch", "main"),
            "portfolioId": payload.get("portfolioId"),
            "loginMode": login_mode,
            "designReviewEnabled": payload.get("designReviewEnabled", False),
            "selfHealEnabled": False,
            "baselineMode": payload.get("baselineMode"),
        }
        if payload.get("designReviewEnabled") and profile == profiles[-1]:
            child_payload["designReviewEnabled"] = True
        logger.info("Suite %s → profile %s", suite_id, profile)
        result = await execute_ui_test(child_id, child_payload)
        results.append(
            {
                "profile": profile,
                "status": result.get("status"),
                "error": result.get("error"),
                "report": result.get("report"),
                "soft_failures": result.get("soft_failures") or [],
                "duration_ms": result.get("duration_ms"),
            }
        )
        if result.get("status") == "FAILED":
            hard_fail += 1
        if result.get("soft_failures"):
            soft_fail += 1

    if hard_fail:
        decision = "NO_GO"
        status = "FAILED"
    elif soft_fail:
        decision = "GO_WITH_CAVEATS"
        status = "GO_WITH_CAVEATS"
    else:
        decision = "GO"
        status = "COMPLETED"

    return {
        "testId": suite_id,
        "status": status,
        "suite": suite_name,
        "decision": decision,
        "loginMode": login_mode,
        "results": results,
        "hard_fail_count": hard_fail,
        "soft_fail_count": soft_fail,
        "targetUrl": target,
    }


async def trigger_vcs_callback(url: str, state: str, description: str) -> None:
    logger.info("VCS callback %s → %s (%s)", url, state, description)


@router.post("/run", response_model=TestRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_test_suite(request: TestRunRequest, background_tasks: BackgroundTasks):
    test_id = str(uuid.uuid4())
    test_runs[test_id] = {"status": "QUEUED", "payload": request.model_dump()}
    background_tasks.add_task(execute_agent_task, test_id, request.model_dump())
    return TestRunResponse(
        testId=test_id,
        status="QUEUED",
        message=f"UI test queued (profile={request.profile}, LLM={settings.LLM_ROUTING}).",
    )


@router.post("/run/auth", response_model=TestRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_auth_flow_test(request: AuthTestRunRequest, background_tasks: BackgroundTasks):
    """Run the predefined am-modern-ui authentication flow (no LLM planner required)."""
    ui_mode = (request.uiMode or settings.UI_APP_MODE).lower()
    if ui_mode == "main":
        profile = "AUTH_FLOW_MAIN"
        target = request.targetUrl or settings.MODERN_UI_MAIN_URL
    else:
        profile = "AUTH_FLOW_PORTFOLIO"
        target = request.targetUrl or settings.MODERN_UI_PORTFOLIO_URL

    payload = {
        "targetUrl": target,
        "specification": "",
        "profile": profile,
        "commitSha": request.commitSha,
        "branch": request.branch,
        "callbackUrl": None,
        "baselineMode": request.baselineMode,
    }
    test_id = str(uuid.uuid4())
    test_runs[test_id] = {"status": "QUEUED", "payload": payload}
    background_tasks.add_task(execute_agent_task, test_id, payload)
    return TestRunResponse(
        testId=test_id,
        status="QUEUED",
        message=f"Auth flow test queued ({profile}) → {target}",
    )


@router.post("/run/profile", response_model=TestRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_profile_test(request: ProfileTestRunRequest, background_tasks: BackgroundTasks):
    if not is_deterministic_profile(request.profile):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown profile {request.profile!r}. Known: {sorted(DETERMINISTIC_PROFILES)}",
        )
    target = request.targetUrl or settings.MODERN_UI_MAIN_URL
    payload = {
        "targetUrl": target,
        "specification": "",
        "profile": request.profile,
        "commitSha": request.commitSha,
        "branch": request.branch,
        "baselineMode": request.baselineMode,
        "portfolioId": request.portfolioId or settings.TEST_PORTFOLIO_ID,
        "loginMode": request.loginMode,
        "persona": request.persona,
        "designReviewEnabled": request.designReviewEnabled,
        "selfHealEnabled": request.selfHealEnabled if request.selfHealEnabled is not None else False,
        "viewportWidth": request.viewportWidth,
        "viewportHeight": request.viewportHeight,
    }
    test_id = str(uuid.uuid4())
    test_runs[test_id] = {"status": "QUEUED", "payload": payload}
    background_tasks.add_task(execute_agent_task, test_id, payload)
    return TestRunResponse(
        testId=test_id,
        status="QUEUED",
        message=f"Profile test queued ({request.profile}) → {target}",
    )


@router.post("/run/suite", response_model=TestRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_suite_test(request: SuiteTestRunRequest, background_tasks: BackgroundTasks):
    if request.suite not in SUITE_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"suite must be one of: {', '.join(sorted(SUITE_PROFILES))}",
        )
    target = request.targetUrl or settings.MODERN_UI_MAIN_URL
    profiles = request.profiles
    if not profiles:
        profiles = list(suite_profiles(request.suite))
    login_mode = request.loginMode
    if request.suite == "prod_ui_full" and (not login_mode or login_mode == "demo"):
        login_mode = "credentials"
    payload = {
        "suite": request.suite,
        "targetUrl": target,
        "profiles": profiles,
        "portfolioId": request.portfolioId or settings.TEST_PORTFOLIO_ID,
        "loginMode": login_mode,
        "commitSha": request.commitSha,
        "branch": request.branch,
        "designReviewEnabled": request.designReviewEnabled,
        "environment": request.environment,
    }
    test_id = str(uuid.uuid4())
    test_runs[test_id] = {"status": "QUEUED", "payload": payload}
    background_tasks.add_task(execute_agent_task, test_id, payload)
    return TestRunResponse(
        testId=test_id,
        status="QUEUED",
        message=f"Suite {request.suite} queued → {target} ({len(profiles)} profiles)",
    )


def _artifact_urls(test_id: str) -> dict[str, str | None]:
    """Stable relative URLs for SPT / external consumers (not host filesystem paths)."""
    report_dir = Path(settings.REPORT_DIR)
    html_path = report_dir / f"{test_id}.html"
    json_path = report_dir / f"{test_id}.json"
    pdf_path = report_dir / f"{test_id}.pdf"
    trace_path = report_dir / "traces" / test_id / "trace.zip"
    prefix = f"/api/v1/test"
    return {
        "reportUrl": f"{prefix}/report/{test_id}" if html_path.is_file() else None,
        "reportJsonUrl": f"{prefix}/report/{test_id}/json" if json_path.is_file() else None,
        "reportPdfUrl": f"{prefix}/report/{test_id}/pdf" if pdf_path.is_file() else None,
        "traceUrl": f"{prefix}/trace/{test_id}" if trace_path.is_file() else None,
    }


def _resolve_report_html_path(test_id: str) -> Path | None:
    if test_id in test_runs and test_runs[test_id].get("report"):
        p = Path(str(test_runs[test_id]["report"]))
        if p.is_file():
            return p
    p = Path(settings.REPORT_DIR) / f"{test_id}.html"
    return p if p.is_file() else None


def _resolve_report_json_path(test_id: str) -> Path | None:
    p = Path(settings.REPORT_DIR) / f"{test_id}.json"
    return p if p.is_file() else None


def _resolve_report_pdf_path(test_id: str) -> Path | None:
    p = Path(settings.REPORT_DIR) / f"{test_id}.pdf"
    return p if p.is_file() else None


def _resolve_trace_path(test_id: str) -> Path | None:
    if test_id in test_runs and test_runs[test_id].get("trace"):
        p = Path(str(test_runs[test_id]["trace"]))
        if p.is_file():
            return p
    p = Path(settings.REPORT_DIR) / "traces" / test_id / "trace.zip"
    return p if p.is_file() else None


@router.get("/profiles")
async def list_profiles():
    flows = []
    for name in sorted(DETERMINISTIC_PROFILES):
        flows.append(
            {
                "id": name,
                "label": name.replace("_", " ").title(),
            }
        )
    return {
        "deterministic": sorted(DETERMINISTIC_PROFILES),
        "release_gate": list(RELEASE_GATE_PROFILES),
        "prod_ui_full": list(PROD_UI_FULL_PROFILES),
        "suites": sorted(SUITE_PROFILES.keys()),
        "flows": flows,
    }


@router.get("/status/{testId}")
async def get_test_status(testId: str):
    if testId not in test_runs:
        raise HTTPException(status_code=404, detail="Test execution ID not found")
    out = dict(test_runs[testId])
    out.update(_artifact_urls(testId))
    return out


@router.get("/report/{testId}")
async def get_test_report_html(testId: str):
    path = _resolve_report_html_path(testId)
    if path is None:
        raise HTTPException(status_code=404, detail="Report not ready yet")
    return FileResponse(path, media_type="text/html", filename=path.name)


@router.get("/report/{testId}/json")
async def get_test_report_json(testId: str):
    path = _resolve_report_json_path(testId)
    if path is None:
        raise HTTPException(status_code=404, detail="Report JSON not ready yet")
    return FileResponse(path, media_type="application/json", filename=path.name)


@router.get("/report/{testId}/pdf")
async def get_test_report_pdf(testId: str):
    path = _resolve_report_pdf_path(testId)
    if path is None:
        raise HTTPException(status_code=404, detail="PDF report not ready yet")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{testId}-report.pdf",
    )


@router.get("/trace/{testId}")
async def get_test_trace_zip(testId: str):
    path = _resolve_trace_path(testId)
    if path is None:
        raise HTTPException(status_code=404, detail="Playwright trace not available")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"{testId}-trace.zip",
    )


@router.get("/screenshot/{testId}/{filename}")
async def get_step_screenshot(testId: str, filename: str):
    """Serve per-step browser evidence PNG captured during execution."""
    from ui_evidence.browser.evidence_paths import resolve_screenshot_dir

    safe = Path(filename).name
    if safe != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid screenshot name")
    if not safe.lower().endswith(".png"):
        raise HTTPException(status_code=400, detail="Only PNG screenshots are served")
    dest_dir = resolve_screenshot_dir(Path(settings.REPORT_DIR), test_id=testId)
    path = dest_dir / safe
    if not path.is_file():
        # Filename may have changed; try matching by step index prefix (001-*.png)
        prefix = safe.split("-", 1)[0] if safe.startswith("step_") is False else ""
        if safe.startswith("step_"):
            # legacy step_001.png -> find 001-*.png
            try:
                n = int(safe.replace("step_", "").replace(".png", ""))
                prefix = f"{n:03d}"
            except ValueError:
                prefix = ""
        if prefix.isdigit() and dest_dir.is_dir():
            matches = sorted(dest_dir.glob(f"{prefix}-*.png"))
            if matches:
                path = matches[0]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(path, media_type="image/png", filename=path.name)
