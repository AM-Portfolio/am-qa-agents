"""One-container entry: HTTP gateway + Temporal worker subprocess."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Any


def _start_worker() -> subprocess.Popen[Any] | None:
    if (os.getenv("QA_AGENT_WORKER_ENABLED") or "1").strip().lower() in {"0", "false", "no"}:
        return None
    return subprocess.Popen(
        [sys.executable, "-m", "orchestrator.worker_main"],
        env=os.environ.copy(),
    )


def main() -> None:
    from composition.env_bootstrap import load_env
    from composition.runtime import apply_colocated_defaults
    from common.observability.logging_setup import configure_logging

    load_env()
    apply_colocated_defaults()
    configure_logging()

    worker = _start_worker()
    host = os.getenv("QA_AGENT_HOST") or os.getenv("APP_HOST") or "0.0.0.0"
    port = int(os.getenv("APP_PORT") or os.getenv("QA_AGENT_PORT") or "8150")

    def _shutdown(*_args: object) -> None:
        if worker and worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=15)
            except subprocess.TimeoutExpired:
                worker.kill()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    import uvicorn

    try:
        uvicorn.run("composition.app:app", host=host, port=port, reload=False)
    finally:
        if worker and worker.poll() is None:
            worker.terminate()


if __name__ == "__main__":
    main()
