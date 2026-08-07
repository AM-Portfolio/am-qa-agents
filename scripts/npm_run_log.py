#!/usr/bin/env python3
"""Run a command, tee stdout/stderr to console + root timestamped .log file.

Usage:
  python scripts/npm_run_log.py ui -- python scripts/with_pythonpath.py python scripts/ui_flow_cli.py auth
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 2 or "--" not in args:
        print(
            "Usage: npm_run_log.py <name> -- <command> [args...]",
            file=sys.stderr,
        )
        return 2
    sep = args.index("--")
    name = (args[0] or "npm").strip().replace(":", "-").replace("/", "-") or "npm"
    cmd = args[sep + 1 :]
    if not cmd:
        print("ERROR: empty command after --", file=sys.stderr)
        return 2

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = ROOT / f"{name}-{stamp}.log"
    header = (
        f"start={datetime.now().isoformat(timespec='seconds')}\n"
        f"cwd={ROOT}\n"
        f"cmd={' '.join(cmd)}\n"
        f"log={log_path}\n"
        f"{'=' * 60}\n"
    )

    print(f"LOG={log_path}", flush=True)
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        log.write(header)
        log.flush()
        env = os.environ.copy()
        env["AM_NPM_RUN_LOG"] = str(log_path)
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()
        rc = proc.wait()
        footer = (
            f"{'=' * 60}\n"
            f"end={datetime.now().isoformat(timespec='seconds')}\n"
            f"exit_code={rc}\n"
        )
        log.write(footer)
        print(f"LOG={log_path} exit={rc}", flush=True)
        return rc


if __name__ == "__main__":
    raise SystemExit(main())
