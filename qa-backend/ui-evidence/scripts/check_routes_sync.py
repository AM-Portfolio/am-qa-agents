#!/usr/bin/env python3
"""Fail if agent routes.py markers drift from am-modern-ui app_routes.dart."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.profiles.modern_ui.routes import DART_SYNC_MARKERS  # noqa: E402

DEFAULT_DART = (
    ROOT.parent.parent
    / "am-modern-ui"
    / "am_app"
    / "lib"
    / "core"
    / "router"
    / "app_routes.dart"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dart-file", type=Path, default=DEFAULT_DART)
    args = parser.parse_args()
    dart = args.dart_file
    if not dart.is_file():
        print(f"SKIP: dart routes not found at {dart}")
        return 0
    text = dart.read_text(encoding="utf-8")
    missing = [m for m in DART_SYNC_MARKERS if m not in text]
    if missing:
        print("ROUTE SYNC FAILED — markers missing from app_routes.dart:")
        for m in missing:
            print(f"  - {m}")
        return 1
    print(f"OK: {len(DART_SYNC_MARKERS)} route markers present in {dart}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
