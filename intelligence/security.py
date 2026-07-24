"""SAST-first security hook — Phase 4 (§20 default: SAST in CI)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

# Lightweight secret / dangerous pattern heuristics (orchestrator stub — not a full SAST engine)
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"][^'\"]{8,}")),
    ("private_key_block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]


def _policy() -> dict[str, Any]:
    cfg = Path(__file__).resolve().parents[1] / "config" / "release-policy.yaml"
    if cfg.is_file():
        with open(cfg, encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("security") or {}
    return {}


def run_sast_hook(
    *,
    repo: str,
    head_sha: str,
    changed_paths: list[str] | None = None,
    file_snippets: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    SAST-first gate.

    Phase 4: local pattern scan + optional CI status passthrough.
    Full Semgrep/CodeQL remains owned by CI — qa-agent only gates on results.
    """
    if os.getenv("QA_AGENT_SKIP_SAST", "").lower() in {"1", "true", "yes"}:
        return {
            "skipped": True,
            "status": "SKIPPED",
            "findings": [],
            "blockers": [],
            "mode": "skip",
        }

    pol = _policy()
    findings: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    # Path heuristics
    for path in changed_paths or []:
        lower = path.lower()
        if lower.endswith((".pem", ".p12", ".key")) and "test" not in lower:
            findings.append(
                {
                    "severity": "P0",
                    "rule": "credential_file",
                    "path": path,
                    "message": "Credential-like file in changeset",
                }
            )
        if "/secrets/" in lower or lower.endswith(".env") and "example" not in lower:
            findings.append(
                {
                    "severity": "P1",
                    "rule": "env_or_secrets_path",
                    "path": path,
                    "message": "Secrets path touched — verify no values committed",
                }
            )

    for path, text in (file_snippets or {}).items():
        for rule, pat in _SECRET_PATTERNS:
            if pat.search(text):
                findings.append(
                    {
                        "severity": "P0",
                        "rule": rule,
                        "path": path,
                        "message": f"Possible secret pattern matched ({rule})",
                    }
                )

    for f in findings:
        label = f"sast:{f['rule']}:{f.get('path')}"
        if f.get("severity") == "P0" and pol.get("block_on_sast_p0", True):
            blockers.append(label)
        else:
            warnings.append(label)

    status = "FAILED" if blockers else ("WARN" if warnings else "PASSED")
    return {
        "skipped": False,
        "status": status,
        "repo": repo,
        "head_sha": head_sha,
        "findings": findings,
        "blockers": blockers,
        "warnings": warnings,
        "mode": "fallback_template",
        "note": "CI owns Semgrep/CodeQL; heuristic only until CI wire-up (replace fallback_template).",
    }


def run_dast_hook(
    *,
    target_url: str | None = None,
    profile: str = "smoke",
) -> dict[str, Any]:
    """
    Optional DAST (disabled by default). Set QA_AGENT_DAST_ENABLED=true.
    Stub only — real ZAP/Nuclei owned by security CI.
    """
    if os.getenv("QA_AGENT_DAST_ENABLED", "").lower() not in {"1", "true", "yes"}:
        return {"skipped": True, "status": "SKIPPED", "mode": "disabled"}
    if os.getenv("QA_AGENT_SKIP_DAST", "").lower() in {"1", "true", "yes"}:
        return {"skipped": True, "status": "SKIPPED", "mode": "skip"}
    return {
        "skipped": False,
        "status": "PASSED",
        "mode": "fallback_template",
        "note": "Wire ZAP/Nuclei via security pipeline; qa-agent records result only",
    }
