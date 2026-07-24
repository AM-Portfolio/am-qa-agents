import base64
import logging
from pathlib import Path

from playwright.async_api import Page

from ui_evidence.config import settings

logger = logging.getLogger(__name__)


async def capture_screenshot_bytes(page: Page) -> bytes:
    png_bytes = await page.screenshot(type="png", full_page=False)
    logger.debug("Captured screenshot (%d bytes)", len(png_bytes))
    return png_bytes


async def capture_screenshot_base64(page: Page) -> str:
    png_bytes = await capture_screenshot_bytes(page)
    return base64.b64encode(png_bytes).decode("ascii")


def step_screenshot_filename(index: int) -> str:
    """1-based index matching step_timings.index."""
    return f"step_{int(index):03d}.png"


def step_screenshot_dir(test_id: str) -> Path:
    return Path(settings.REPORT_DIR) / "screenshots" / test_id


def step_screenshot_url(test_id: str, index: int) -> str:
    return f"/api/v1/test/screenshot/{test_id}/{step_screenshot_filename(index)}"


async def capture_and_save_step_screenshot(
    page: Page,
    *,
    test_id: str,
    index: int,
) -> tuple[str, str, str]:
    """
    Capture PNG for a browser step.

    Returns (base64, relative_api_url, absolute_file_path).
    ``index`` is 0-based executor index; file uses 1-based step number.
    """
    png_bytes = await capture_screenshot_bytes(page)
    encoded = base64.b64encode(png_bytes).decode("ascii")
    dest_dir = step_screenshot_dir(test_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    step_no = index + 1
    dest = dest_dir / step_screenshot_filename(step_no)
    dest.write_bytes(png_bytes)
    url = step_screenshot_url(test_id, step_no)
    return encoded, url, str(dest.resolve())
