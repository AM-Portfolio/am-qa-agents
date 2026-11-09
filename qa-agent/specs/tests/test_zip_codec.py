"""Payload zip/gzip codec for compressed import/export."""

from __future__ import annotations

import base64
import unittest

from specs.payloads.zip_codec import (
    ZipCodecError,
    maybe_expand_import_fields,
    pack_gzip,
    pack_zip,
    unpack_blob,
)


class ZipCodecTests(unittest.TestCase):
    def test_roundtrip_zip(self) -> None:
        doc = {"format": "am-specs-dataset", "payload_set": {"apis": {"a": {"method": "GET"}}}}
        blob = pack_zip(doc)
        self.assertTrue(blob.startswith(b"PK"))
        self.assertLess(len(blob), 500)
        out = unpack_blob(blob, filename="pack.zip")
        self.assertEqual(out["payload_set"]["apis"]["a"]["method"], "GET")

    def test_roundtrip_gzip(self) -> None:
        doc = {"hello": "world", "n": list(range(50))}
        blob = pack_gzip(doc)
        self.assertEqual(blob[:2], b"\x1f\x8b")
        self.assertEqual(unpack_blob(blob), doc)

    def test_expand_zip_b64(self) -> None:
        inner = {"service": "am-market-data", "payload_set": {"apis": {"x": {}}}}
        b64 = base64.b64encode(pack_zip(inner)).decode("ascii")
        expanded = maybe_expand_import_fields(
            {"service": "am-market-data", "zip_b64": b64}
        )
        self.assertIn("payload_set", expanded)
        self.assertEqual(expanded["payload_set"]["apis"]["x"], {})

    def test_bad_zip(self) -> None:
        with self.assertRaises(ZipCodecError):
            unpack_blob(b"not-a-zip", filename="x.zip")


if __name__ == "__main__":
    unittest.main()
