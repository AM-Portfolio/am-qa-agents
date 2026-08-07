import base64
import logging
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page

from ui_evidence.browser.evidence_paths import (
    evidence_run_dirname,
    resolve_screenshot_dir,
    step_screenshot_filename,
)
from ui_evidence.config import settings

logger = logging.getLogger(__name__)


async def capture_screenshot_bytes(page: Page) -> bytes:
    png_bytes = await page.screenshot(type="png", full_page=False)
    logger.debug("Captured screenshot (%d bytes)", len(png_bytes))
    return png_bytes


async def capture_screenshot_base64(page: Page) -> str:
    png_bytes = await capture_screenshot_bytes(page)
    return base64.b64encode(png_bytes).decode("ascii")


def step_screenshot_dir(
    test_id: str,
    *,
    evidence_dirname: str | None = None,
    profile: str | None = None,
) -> Path:
    dirname = evidence_dirname
    if not dirname and profile:
        dirname = evidence_run_dirname(profile, test_id)
    return resolve_screenshot_dir(
        Path(settings.REPORT_DIR),
        test_id=test_id,
        evidence_dirname=dirname,
    )


def step_screenshot_url(test_id: str, filename: str) -> str:
    return f"/api/v1/test/screenshot/{test_id}/{filename}"


async def capture_and_save_step_screenshot(
    page: Page,
    *,
    test_id: str,
    index: int,
    step_name: str | None = None,
    evidence_dirname: str | None = None,
    profile: str | None = None,
) -> tuple[str, str, str]:
    """
    Capture PNG for a browser step.

    Saves under screenshots/{prefix}-{YYYYMMDD-HHMMSS}-{shortId}/
    as {NNN}-{HHMMSS}-{step-slug}.png

    Returns (base64, relative_api_url, absolute_file_path).
    ``index`` is 0-based executor index; file uses 1-based step number.
    """
    captured_at = datetime.now()
    png_bytes = await capture_screenshot_bytes(page)
    encoded = base64.b64encode(png_bytes).decode("ascii")
    dest_dir = step_screenshot_dir(
        test_id,
        evidence_dirname=evidence_dirname,
        profile=profile,
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    step_no = index + 1
    filename = step_screenshot_filename(step_no, step_name=step_name, when=captured_at)
    dest = dest_dir / filename
    dest.write_bytes(png_bytes)
    url = step_screenshot_url(test_id, filename)
    logger.info("Screenshot saved -> %s", dest)
    return encoded, url, str(dest.resolve())
