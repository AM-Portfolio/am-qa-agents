"""Composition runtime — one-pod env defaults (loopback UI)."""
from __future__ import annotations

import os


def apply_colocated_defaults() -> None:
    """When running unified backend, point SPT/release at in-process UI via loopback."""
    port = os.getenv("APP_PORT") or os.getenv("QA_AGENT_PORT") or "8150"
    loopback = f"http://127.0.0.1:{port}"
    # SPT → UI evidence (same container; Traefik /ui-test still works externally)
    os.environ.setdefault("SPT_UI_TEST_AGENT_URL", loopback)
    os.environ.setdefault("UI_TEST_AGENT_URL", loopback)
    os.environ.setdefault("UI_TEST_AGENT_BASE_URL", loopback)
    # Prefer not hairpinning public /ui-test from inside the pod
    if not os.getenv("QA_AGENT_COLOCATED"):
        os.environ["QA_AGENT_COLOCATED"] = "1"
