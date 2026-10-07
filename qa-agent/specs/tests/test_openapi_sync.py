"""Runtime OpenAPI sync cache (no per-service git catalogs)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from specs.catalog import openapi_sync as sync


class OpenApiSyncTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sync.settings, "data_dir", tmp):
                doc = {
                    "openapi": "3.0.3",
                    "info": {"title": "demo", "version": "1"},
                    "paths": {
                        "/health": {"get": {"operationId": "health", "responses": {"200": {"description": "ok"}}}},
                        "/items": {"get": {"operationId": "list_items", "responses": {"200": {"description": "ok"}}}},
                    },
                }
                saved = sync.save_synced_openapi(
                    "am-demo",
                    "dev",
                    document=doc,
                    openapi_url="https://example.test/openapi.json",
                    target_url="https://example.test",
                    apis=[{"id": "health", "method": "GET", "path": "/health"}],
                )
                self.assertEqual(saved["path_count"], 2)
                self.assertTrue(Path(tmp, "openapi_sync", "am-demo", "dev.json").is_file())

                loaded = sync.load_synced_openapi("am-demo", "dev")
                assert loaded is not None
                self.assertEqual(loaded["title"], "demo")
                self.assertIn("/items", loaded["document"]["paths"])
                self.assertEqual(len(loaded["apis"]), 1)

    def test_missing_sync_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sync.settings, "data_dir", tmp):
                self.assertIsNone(sync.load_synced_openapi("nope", "dev"))


if __name__ == "__main__":
    unittest.main()
