"""Tests for HTML → PDF report generation."""
from __future__ import annotations

from pathlib import Path

import pytest

from ui_evidence.agent.report_pdf import write_report_pdf


@pytest.mark.asyncio
async def test_write_report_pdf(tmp_path: Path):
    html = tmp_path / "report.html"
    pdf = tmp_path / "report.pdf"
    html.write_text(
        "<!DOCTYPE html><html><body><h1>UI Test Report</h1>"
        "<p>Complete report for PDF export</p></body></html>",
        encoding="utf-8",
    )
    out = await write_report_pdf(html_path=html, pdf_path=pdf)
    assert out is not None
    assert pdf.is_file()
    assert pdf.stat().st_size > 100
    # PDF magic
    assert pdf.read_bytes()[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_write_report_pdf_missing_html(tmp_path: Path):
    out = await write_report_pdf(
        html_path=tmp_path / "missing.html",
        pdf_path=tmp_path / "out.pdf",
    )
    assert out is None
