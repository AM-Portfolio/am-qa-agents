"""Load qa-agent .env and normalize aliases from am-agents lab env."""

from __future__ import annotations

import os
from pathlib import Path


def _qa_agent_root() -> Path:
    # composition/env_bootstrap.py → qa-agent/
    return Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    # am-qa-agents monorepo root
    return Path(__file__).resolve().parents[2]


def load_env(*, override: bool = False) -> Path | None:
    """
    Load `.env` from qa-agent/ (preferred), then monorepo root / cwd.

    Also maps am-agents-style aliases so one lab env pattern works.
    Skipped in-cluster (KUBERNETES_SERVICE_HOST) — Helm/Vault own config.
    """
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        _apply_aliases()
        return None

    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment]

    loaded: Path | None = None
    candidates = [
        _qa_agent_root() / ".env",
        _repo_root() / ".env",
        Path.cwd() / ".env",
    ]
    if load_dotenv:
        for path in candidates:
            if path.is_file():
                try:
                    load_dotenv(path, override=override)
                    loaded = path
                    break
                except UnicodeDecodeError:
                    # Local .env with non-UTF8 bytes — skip rather than crash
                    continue
    else:
        loaded = next((p for p in candidates if p.is_file()), None)

    _apply_aliases()
    return loaded


def _apply_aliases() -> None:
    """Copy shared lab keys into qa-agent expected names when unset."""
    pairs = [
        ("TOOL_AGENT_URL", "TOOL_AGENT_BASE_URL"),
        ("TOOL_AGENT_BASE_URL", "TOOL_AGENT_URL"),
        ("LITELLM_MASTER_KEY", "QA_AGENT_LLM_API_KEY"),
        ("LITELLM_MASTER_KEY", "OPENAI_API_KEY"),
        ("LITELLM_BASE_URL", "OPENAI_BASE_URL"),
        ("SUPPORT_AGENT_DATABASE_URL", "QA_AGENT_DATABASE_URL"),
        ("RUN_STORE_DSN", "QA_AGENT_DATABASE_URL"),
        # Specs + release-gate share one Postgres DSN when only one is set
        ("QA_AGENT_DATABASE_URL", "SPT_DATABASE_URL"),
        ("SPT_DATABASE_URL", "QA_AGENT_DATABASE_URL"),
        ("GROWTHBOOK_CLIENT_KEY", "GROWTHBOOK_API_KEY"),
        ("ZOHO_CLIQ_WEBHOOK_URL", "QA_AGENT_CLIQ_WEBHOOK_URL"),
        ("OPENPROJECT_PROJECT_ID", "QA_AGENT_OP_PROJECT_ID"),
        ("PROMETHEUS_URL", "QA_AGENT_PROMETHEUS_URL"),
        ("MINIO_ENDPOINT", "QA_AGENT_MINIO_ENDPOINT"),
        ("MINIO_ACCESS_KEY", "QA_AGENT_MINIO_ACCESS_KEY"),
        ("MINIO_SECRET_KEY", "QA_AGENT_MINIO_SECRET_KEY"),
        ("MINIO_BUCKET", "QA_AGENT_MINIO_BUCKET"),
        ("GRAFANA_EXTERNAL_URL", "QA_AGENT_GRAFANA_URL"),
    ]
    for src, dst in pairs:
        if os.getenv(src) and not os.getenv(dst):
            os.environ[dst] = os.environ[src]

    # OpenProject project name fallback for work items
    if not os.getenv("QA_AGENT_OP_PROJECT") and os.getenv("OPENPROJECT_PROJECT_ID"):
        os.environ["QA_AGENT_OP_PROJECT"] = os.environ["OPENPROJECT_PROJECT_ID"]

    # Default LiteLLM model
    if not os.getenv("LLM_MODEL") and not os.getenv("QA_AGENT_LLM_MODEL"):
        os.environ.setdefault("QA_AGENT_LLM_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
    elif os.getenv("LLM_MODEL") and not os.getenv("QA_AGENT_LLM_MODEL"):
        os.environ["QA_AGENT_LLM_MODEL"] = os.environ["LLM_MODEL"]
