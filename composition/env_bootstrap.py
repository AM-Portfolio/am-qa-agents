"""Load qa-agent .env and normalize aliases from am-agents lab env."""

from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_env(*, override: bool = False) -> Path | None:
    """
    Load `.env` from qa-agent repo root (gitignored).

    Also maps am-agents-style aliases so one lab env pattern works.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment]

    root = _repo_root()
    path = root / ".env"
    if load_dotenv and path.is_file():
        load_dotenv(path, override=override)
    elif load_dotenv:
        # Allow cwd .env when running from elsewhere
        cwd_env = Path.cwd() / ".env"
        if cwd_env.is_file():
            load_dotenv(cwd_env, override=override)
            path = cwd_env
        else:
            path = None
    else:
        path = path if path.is_file() else None

    _apply_aliases()
    return path


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
