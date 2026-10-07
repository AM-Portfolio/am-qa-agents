"""Unit tests for GET /api/services/{key}/overview aggregate."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class ServiceOverviewTests(unittest.TestCase):
    @patch("specs.services.service_overview._plugin_use_cases", return_value=[])
    @patch("specs.services.service_overview.list_runs")
    @patch("specs.services.service_overview.list_payload_sets")
    @patch("specs.services.service_overview.get_payload_set")
    @patch("specs.services.service_overview.load_openapi_document")
    @patch("specs.services.service_overview.reachable_target_for_service")
    @patch("specs.services.service_overview.load_service_apis")
    @patch("specs.services.service_overview.load_registration")
    @patch("specs.services.service_overview._plugin_summary")
    @patch("specs.services.service_overview._bank_sections")
    @patch("specs.services.service_overview.load_platform_skills")
    def test_build_shape(
        self,
        mock_skills: MagicMock,
        mock_bank: MagicMock,
        mock_plugin: MagicMock,
        mock_reg: MagicMock,
        mock_apis: MagicMock,
        mock_target: MagicMock,
        mock_oas: MagicMock,
        mock_get_set: MagicMock,
        mock_sets: MagicMock,
        mock_runs: MagicMock,
        _mock_plugin_cases: MagicMock,
    ) -> None:
        mock_reg.return_value = {
            "service": "am-subscription",
            "label": "Subscription",
            "runtime": "java",
        }
        mock_apis.return_value = {
            "apis": [{"id": "a"}, {"id": "b"}],
            "runtime": "java",
            "openapi_version": "3.0.1",
        }
        mock_target.return_value = "https://subscription-dev.example"
        mock_oas.return_value = {
            "ok": True,
            "openapi_url": "https://subscription-dev.example/v3/api-docs",
            "path_count": 12,
            "operation_count": 20,
            "version": "1.0",
            "title": "Sub",
            "document": {"paths": {}},
        }
        mock_sets.return_value = {
            "service": "am-subscription",
            "active_version": 2,
            "sets": [{"version": 2}],
            "count": 1,
        }
        mock_get_set.return_value = {"label": "working", "apis": {"x": {}, "y": {}}}
        mock_plugin.return_value = {
            "id": "am-subscription",
            "enabled": True,
            "api_pack": "subscription_smoke",
        }
        mock_skills.return_value = [
            {"id": "happy_flow", "level": "L1", "env_policy": {"dev": "run"}},
            {"id": "validation", "level": "L2", "env_policy": {"dev": "run"}},
        ]
        mock_bank.return_value = (
            {"skill_overlays": {"happy_flow": "note"}},
            [{"feature_id": "f1", "title": "Checkout", "scenarios_count": 3}],
            {
                "count": 5,
                "invent_complete": True,
                "needs_reinvent": False,
                "by_skill": {"happy_flow": 3, "validation": 2},
            },
            {"quality_score": 7.5, "reasons": ["ok"]},
            [
                {
                    "title": "Checkout happy",
                    "skill": "happy_flow",
                    "steps": [{"method": "get", "path": "/plans"}],
                }
            ],
            None,
        )
        mock_runs.return_value = (
            [
                {
                    "id": "run-1",
                    "status": "passed",
                    "passed": True,
                    "triggered_by": "ops",
                    "service": "am-subscription",
                    "environment": "dev",
                    "p90_ms": 120.0,
                    "fail_pct": 0.0,
                    "rps": 10.0,
                    "config_name": "smoke",
                }
            ],
            1,
        )

        from specs.services.service_overview import build_service_overview

        out = build_service_overview("am-subscription", environment="dev", runs_limit=10)
        self.assertTrue(out["ok"])
        self.assertEqual(out["service"]["id"], "am-subscription")
        # Default overview skips live OpenAPI (fast path) — uses baked/stub counts
        self.assertIn("apis_count", out["catalog"])
        self.assertTrue(out["openapi"].get("live_skipped") or out["openapi"].get("ok") is not None)
        self.assertEqual(out["payloads"]["api_count"], 2)
        self.assertEqual(out["scenarios"]["count"], 5)
        self.assertEqual(len(out["features"]), 1)
        self.assertEqual(out["runs"][0]["id"], "run-1")
        self.assertEqual(out["metrics"]["recent_pass_rate"], 100.0)
        skill_ids = {s["id"] for s in out["skills"]}
        self.assertIn("happy_flow", skill_ids)
        happy = next(s for s in out["skills"] if s["id"] == "happy_flow")
        self.assertEqual(happy["bank_count"], 3)
        self.assertEqual(happy.get("display_name"), "Happy path validation")
        self.assertTrue(
            any(u.get("source") in ("bank_scenario", "bank_feature") for u in out["use_cases"])
        )
        self.assertFalse(out["partial"])

    @patch("specs.services.service_overview._plugin_use_cases", return_value=[])
    @patch("specs.services.service_overview.list_runs", side_effect=RuntimeError("store down"))
    @patch("specs.services.service_overview.list_payload_sets", return_value={"count": 0, "sets": []})
    @patch("specs.services.service_overview.get_payload_set", return_value=None)
    @patch(
        "specs.services.service_overview.load_openapi_document",
        return_value={"ok": False, "error": "unreachable"},
    )
    @patch(
        "specs.services.service_overview.reachable_target_for_service",
        return_value=None,
    )
    @patch(
        "specs.services.service_overview.load_service_apis",
        return_value={"apis": []},
    )
    @patch("specs.services.service_overview.load_registration", return_value=None)
    @patch("specs.services.service_overview._plugin_summary", return_value=None)
    @patch(
        "specs.services.service_overview._bank_sections",
        return_value=(
            None,
            [],
            {"count": 0, "invent_complete": False, "by_skill": {}},
            {},
            [],
            "mongo timeout",
        ),
    )
    @patch("specs.services.service_overview.load_platform_skills", return_value=[])
    def test_partial_on_failures(self, *_mocks: MagicMock) -> None:
        from specs.services.service_overview import build_service_overview

        out = build_service_overview("unknown-svc", environment="dev")
        self.assertTrue(out["ok"])
        self.assertTrue(out["partial"])
        self.assertTrue(any("bank" in w for w in out["warnings"]))
        self.assertTrue(any("runs" in w for w in out["warnings"]))
        self.assertEqual(out["runs"], [])


if __name__ == "__main__":
    unittest.main()
