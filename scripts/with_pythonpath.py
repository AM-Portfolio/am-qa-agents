"""Set PYTHONPATH then exec remaining argv as a subprocess (Windows-friendly)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["PYTHONPATH"] = str(ROOT / "qa-agent") + os.pathsep + str(ROOT / "qa-agent" / "release_gate")
os.environ.setdefault("QA_AGENT_WORKER_ENABLED", "0")

if len(sys.argv) < 2:
    print("usage: python scripts/with_pythonpath.py <cmd> [args...]", file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(subprocess.call(sys.argv[1:], cwd=str(ROOT)))
