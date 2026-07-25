"""Tests for catalog-ready race guard."""

from __future__ import annotations

from adapters.catalog_ready import requires_spt_catalog


def test_ui_only_skips_catalog() -> None:
    assert requires_spt_catalog("am-modern-ui") is False


def test_backend_requires_catalog() -> None:
    assert requires_spt_catalog("am-analysis") is True
    assert requires_spt_catalog("am-gateway") is True


def test_empty_service_no_catalog() -> None:
    assert requires_spt_catalog(None) is False
    assert requires_spt_catalog("") is False
