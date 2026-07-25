"""Unit tests for SPT UI catalog store merge + resolve_ui_run."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from specs.ui_bridge.ui_flow_catalog import build_ui_flow_catalog


class UiCatalogStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmpdir.name)
        self._settings_patch = mock.patch("specs.ui_bridge.ui_catalog_store.settings")
        self.settings = self._settings_patch.start()
        self.settings.data_dir = str(self.data_dir)

    def tearDown(self) -> None:
        self._settings_patch.stop()
        self._tmpdir.cleanup()

    def test_merge_custom_flow_and_override(self) -> None:
        from specs.ui_bridge.ui_catalog_store import merge_catalog, upsert_flow

        upsert_flow(
            {
                "id": "MY_ALIAS",
                "label": "My alias",
                "group": "Custom",
                "summary": "alias",
                "steps": ["a"],
                "verifications": ["b"],
                "runs_as": "PORTFOLIO_SMOKE_FLOW",
            },
            create=True,
        )
        upsert_flow(
            {
                "id": "PORTFOLIO_SMOKE_FLOW",
                "label": "Portfolio overview (edited)",
                "summary": "overridden",
            },
            create=False,
        )
        base = build_ui_flow_catalog(agent_online=False)
        merged = merge_catalog(base)
        custom = next(f for f in merged["flows"] if f["id"] == "MY_ALIAS")
        self.assertTrue(custom["custom"])
        self.assertTrue(custom["deletable"])
        self.assertEqual(custom["runs_as"], "PORTFOLIO_SMOKE_FLOW")
        builtin = next(f for f in merged["flows"] if f["id"] == "PORTFOLIO_SMOKE_FLOW")
        self.assertEqual(builtin["label"], "Portfolio overview (edited)")
        self.assertTrue(builtin["resettable"])
        self.assertFalse(builtin["deletable"])

    def test_resolve_custom_flow_and_suite(self) -> None:
        from specs.ui_bridge.ui_catalog_store import resolve_ui_run, upsert_flow, upsert_suite

        upsert_flow(
            {
                "id": "MY_ALIAS",
                "label": "My alias",
                "runs_as": "PORTFOLIO_SMOKE_FLOW",
            },
            create=True,
        )
        upsert_suite(
            {
                "id": "nightly_core",
                "label": "Nightly",
                "profiles": ["AUTH_FLOW_MAIN", "MY_ALIAS"],
                "agent_suite": "smoke",
            },
            create=True,
        )
        flow_cfg = resolve_ui_run({"ui_profile": "MY_ALIAS", "ui_suite": None})
        self.assertEqual(flow_cfg["ui_profile"], "PORTFOLIO_SMOKE_FLOW")
        self.assertEqual(flow_cfg["ui_profile_requested"], "MY_ALIAS")

        suite_cfg = resolve_ui_run({"ui_suite": "nightly_core", "ui_profile": None})
        self.assertEqual(suite_cfg["ui_suite"], "smoke")
        self.assertEqual(suite_cfg["ui_suite_requested"], "nightly_core")
        self.assertEqual(
            suite_cfg["ui_profiles"],
            ["AUTH_FLOW_MAIN", "PORTFOLIO_SMOKE_FLOW"],
        )

    def test_reject_unknown_runs_as(self) -> None:
        from specs.ui_bridge.ui_catalog_store import UiCatalogError, upsert_flow

        with self.assertRaises(UiCatalogError):
            upsert_flow(
                {"id": "BAD", "label": "Bad", "runs_as": "NOT_A_REAL_FLOW"},
                create=True,
            )


if __name__ == "__main__":
    unittest.main()
