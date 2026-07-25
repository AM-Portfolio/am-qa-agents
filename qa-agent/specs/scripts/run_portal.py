#!/usr/bin/env python3
"""Start SPT portal locally with env-specific public hosts (npm run spt:*)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Laptop → public HTTPS (not in-cluster DNS). Auth credentials stay in .env.
# Product URLs derive from DEFAULT_ENVIRONMENT / APP_ENV when unset.
ENV_PRESETS: dict[str, dict[str, str]] = {
    "local": {
        # Use .env as-is (DEFAULT_ENVIRONMENT / identity already set there).
    },
    "dev": {
        "APP_ENV": "dev",
        "DEFAULT_ENVIRONMENT": "dev",
    },
    "preprod": {
        "APP_ENV": "preprod",
        "DEFAULT_ENVIRONMENT": "preprod",
    },
    "prod": {
        "APP_ENV": "prod",
        "DEFAULT_ENVIRONMENT": "prod",
    },
}


def _venv_python() -> Path:
    if sys.platform == "win32":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SPT portal for a target environment")
    parser.add_argument(
        "--env",
        choices=sorted(ENV_PRESETS.keys()),
        default="local",
        help="Target AM environment (default: local = .env as-is)",
    )
    parser.add_argument("--port", type=int, default=None, help="Override APP_PORT (default from .env / 8150)")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn --reload")
    args = parser.parse_args()

    if not (ROOT / ".env").is_file():
        example = ROOT / ".env.example"
        if example.is_file():
            print(f"Missing {ROOT / '.env'} — copy from .env.example and set SPT_AUTH_PASSWORD", file=sys.stderr)
        else:
            print(f"Missing {ROOT / '.env'}", file=sys.stderr)
        return 1

    py = _venv_python()
    if not py.is_file():
        py = Path(sys.executable)
        print(f">>> No .venv at {ROOT / '.venv'} — using {py}", flush=True)

    env = os.environ.copy()
    # Always laptop portal URL when started via npm
    env.setdefault("SPT_PUBLIC_BASE_URL", "http://localhost:8150")
    env.update(ENV_PRESETS[args.env])

    port = str(args.port or env.get("APP_PORT") or "8150")
    cmd = [
        str(py),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        port,
    ]
    if not args.no_reload:
        cmd.append("--reload")

    default_env = env.get("DEFAULT_ENVIRONMENT", "(from .env)")
    identity = env.get("SPT_IDENTITY_URL", "(from .env)")
    print(f">>> SPT portal env={args.env} DEFAULT_ENVIRONMENT={default_env}", flush=True)
    print(f">>> identity={identity}", flush=True)
    print(f">>> http://localhost:{port}/ui\n", flush=True)
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
