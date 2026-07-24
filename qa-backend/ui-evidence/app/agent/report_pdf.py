"""Render the complete UI test HTML report to PDF via Playwright Chromium."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


async def write_report_pdf(*, html_path: Path, pdf_path: Path) -> Path | None:
    """
    Print the report HTML to a PDF file.

    Returns pdf_path on success, None if generation fails (non-fatal for the run).
    """
    if not html_path.is_file():
        logger.warning("PDF skipped — HTML report missing: %s", html_path)
        return None

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("PDF skipped — playwright not installed")
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            try:
                page = await browser.new_page()
                await page.goto(
                    html_path.resolve().as_uri(),
                    wait_until="networkidle",
                    timeout=60_000,
                )
                await page.pdf(
                    path=str(pdf_path),
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "12mm",
                        "bottom": "12mm",
                        "left": "10mm",
                        "right": "10mm",
                    },
                )
            finally:
                await browser.close()
    except Exception:
        logger.exception("Failed to generate PDF report for %s", html_path)
        if pdf_path.is_file():
            pdf_path.unlink(missing_ok=True)
        return None

    if pdf_path.is_file() and pdf_path.stat().st_size > 0:
        logger.info("PDF report written → %s (%s bytes)", pdf_path, pdf_path.stat().st_size)
        return pdf_path
    return None
