"""LoadContext resolver — Phase 1 (§12)."""

from __future__ import annotations

import fnmatch
import os
import uuid
from pathlib import Path
from typing import Any

import yaml


def _config_dir() -> Path:
    env = os.getenv("QA_AGENT_CONFIG_DIR")
    if env:
        return Path(env)
    # src/am_qa_agent/intelligence → repo config/
    return Path(__file__).resolve().parents[1] / "config"


def _load_yaml(name: str) -> dict[str, Any]:
    path = _config_dir() / name
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _match_pattern(value: str, pattern: str) -> bool:
    return fnmatch.fnmatch(value, pattern)


def _path_matches(path: str, pattern: str) -> bool:
    """fnmatch with light ** support for load-rules."""
    if fnmatch.fnmatch(path, pattern):
        return True
    # **/*.md → also match bare *.md at root
    if pattern.startswith("**/"):
        return fnmatch.fnmatch(path, pattern[3:]) or fnmatch.fnmatch(path, pattern)
    return False


def _any_path_match(paths: list[str], patterns: list[str]) -> bool:
    return any(any(_path_matches(p, pat) for pat in patterns) for p in paths)


def _all_paths_match(paths: list[str], patterns: list[str]) -> bool:
    return bool(paths) and all(any(_path_matches(p, pat) for pat in patterns) for p in paths)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if k == "inherits":
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve_env_block(branch: str, env_override: str | None = None) -> tuple[str, dict[str, Any]]:
    raw = _load_yaml("environments.yaml")
    envs: dict[str, Any] = raw.get("environments") or {}
    if env_override and env_override in envs:
        name = env_override
    else:
        name = "local"
        for env_name, block in envs.items():
            patterns = block.get("branch_patterns") or []
            if any(_match_pattern(branch, p) for p in patterns):
                name = env_name
                break
    block = dict(envs.get(name) or {})
    inherits = block.get("inherits")
    if inherits and inherits in envs:
        block = _deep_merge(dict(envs[inherits]), block)
    return name, block


def _repo_short(repo: str) -> str:
    # am/am-market or am-market → am-market
    return repo.split("/")[-1] if repo else ""


def apply_load_rules(
    *,
    repo: str,
    changed_paths: list[str] | None = None,
    env_block: dict[str, Any],
) -> dict[str, Any]:
    rules_doc = _load_yaml("load-rules.yaml")
    rules = rules_doc.get("rules") or []
    default = rules_doc.get("default") or {}
    short = _repo_short(repo)
    paths = changed_paths or []

    selected = None
    docs_candidate = None
    for rule in rules:
        match = rule.get("match") or {}
        repos = match.get("repos") or []
        paths_any = match.get("paths_any") or []
        repo_ok = not repos or short in repos or repo in repos
        if rule.get("docs_only"):
            if paths and _all_paths_match(paths, paths_any or ["**/*.md", "**/docs/**", "*.md"]):
                docs_candidate = rule
            continue
        path_ok = True
        if paths_any:
            path_ok = _any_path_match(paths, paths_any) if paths else False
        if repo_ok and (not paths_any or path_ok):
            if paths_any and path_ok:
                selected = rule
                break
            if not paths_any and selected is None:
                selected = rule
    if docs_candidate is not None:
        selected = docs_candidate
    if selected is None:
        selected = {"fin_services": default.get("fin_services"), **default}

    service_map = env_block.get("service_map") or {}
    fin_names = selected.get("fin_services")
    if fin_names is None:
        fin_names = default.get("fin_services") or list(service_map.keys())
    services = []
    for name in fin_names:
        meta = service_map.get(name) or {}
        services.append(
            {
                "name": name,
                "base_url": meta.get("base_url", ""),
                "spec_url": meta.get("spec_url", ""),
            }
        )

    ui_target_name = selected.get("ui_target") or default.get("ui_target") or "main"
    ui_targets = env_block.get("ui_targets") or {}
    ui_t = ui_targets.get(ui_target_name) or ui_targets.get("main") or {}
    profile = (
        selected.get("ui_profile")
        or ui_t.get("profile")
        or env_block.get("default_ui_profile")
        or default.get("ui_profile")
        or "SMOKE"
    )

    return {
        "fin_services": services,
        "scenarios": selected.get("scenarios") or default.get("scenarios") or [],
        "ui_target_name": ui_target_name,
        "ui_target": ui_t,
        "ui_profile": profile,
        "docs_only": bool(selected.get("docs_only")),
        "rule": selected,
    }


def _hydrate_service_from_spt(service: str, environment: str) -> dict[str, Any] | None:
    """Fill fin service base_url/spec_url from existing am.spt/v1 registration (spt.yaml)."""
    try:
        from specs.catalog.catalog_loader import load_registration, reachable_target_for_service
    except ImportError:
        return None

    reg = load_registration(service)
    if not reg or reg.get("enabled") is False:
        return None

    base = ""
    try:
        base = str(reachable_target_for_service(service, environment) or "").rstrip("/")
    except Exception:  # noqa: BLE001 — fall back to targets map
        base = ""
    if not base:
        targets = reg.get("targets") if isinstance(reg.get("targets"), dict) else {}
        base = str(targets.get(environment) or targets.get("dev") or "").rstrip("/")

    oas = reg.get("openapi") if isinstance(reg.get("openapi"), dict) else {}
    runtime = str(reg.get("runtime") or "java")
    path = str(oas.get("path") or ("/openapi.json" if runtime == "python" else "/v3/api-docs"))
    if not path.startswith("/"):
        path = f"/{path}"
    spec_url = f"{base}{path}" if base else ""

    return {
        "name": service,
        "base_url": base,
        "spec_url": spec_url,
        "runtime": runtime,
        "source": "spt_registration",
        "spt_label": reg.get("label") or service,
    }


def resolve_load_profile(
    *,
    tracking_id: str,
    repo: str,
    branch: str,
    head_sha: str,
    base_sha: str | None = None,
    environment: str | None = None,
    changed_paths: list[str] | None = None,
    callback_url: str | None = None,
    service: str | None = None,
) -> dict[str, Any]:
    env_name, block = resolve_env_block(branch, environment)
    paths = list(changed_paths or [])
    svc = (service or "").strip()

    applied = apply_load_rules(repo=repo, changed_paths=paths, env_block=block)

    # CI / notify service hint: prefer existing SPT registration (spt.yaml) over empty load-rules.
    if svc:
        applied["scenarios"] = list(
            dict.fromkeys([*(applied.get("scenarios") or []), "health_smoke", "contract_smoke"])
        )
        hydrated = _hydrate_service_from_spt(svc, env_name)
        if hydrated:
            others = [
                s
                for s in (applied.get("fin_services") or [])
                if isinstance(s, dict) and s.get("name") != svc
            ]
            applied["fin_services"] = [hydrated, *others]
        elif not any(
            isinstance(s, dict) and s.get("name") == svc for s in (applied.get("fin_services") or [])
        ):
            # Keep service name so SPT execute / catalog wait still have a target id
            applied["fin_services"] = [
                {"name": svc, "base_url": "", "spec_url": "", "source": "service_hint"},
                *(applied.get("fin_services") or []),
            ]

    ui_t = applied["ui_target"]
    lc = {
        "load_context_id": f"lc-{uuid.uuid4().hex[:10]}",
        "tracking_id": tracking_id,
        "environment": env_name,
        "service": service,
        "webhook": {
            "repo": repo,
            "branch": branch,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "changed_paths": paths,
        },
        "fin": {
            "services": applied["fin_services"],
            "scenarios": applied["scenarios"]
            or ["health_smoke", "contract_smoke"],
            "impacted_ops": [],
        },
        "ui": {
            "target_name": applied["ui_target_name"],
            "target_url": ui_t.get("base_url") or os.getenv("QA_AGENT_SMOKE_TARGET_URL", ""),
            "ui_mode": ui_t.get("ui_mode") or "main",
            "profile": applied["ui_profile"],
            "specification": "",
            "auth_login_mode": ui_t.get("auth_login_mode") or "demo",
            "baseline_mode": "compare",
        },
        "github": {"callback_url": callback_url},
        "credential_refs": block.get("credential_refs") or {},
        "routing": {
            # Env wins over YAML so local/.env domains are not overridden by localhost placeholders.
            "fin_agent_base_url": os.getenv("FIN_AGENT_BASE_URL")
            or block.get("fin_agent_base_url")
            or "http://127.0.0.1:8100",
            "ui_test_agent_base_url": os.getenv("UI_TEST_AGENT_BASE_URL")
            or block.get("ui_test_agent_base_url")
            or "http://127.0.0.1:8130",
            "tool_agent_base_url": os.getenv("TOOL_AGENT_BASE_URL")
            or os.getenv("TOOL_AGENT_URL")
            or block.get("tool_agent_base_url")
            or "http://127.0.0.1:8141",
            "gnx_mcp_url": os.getenv("GNX_MCP_URL")
            or block.get("gnx_mcp_url")
            or "http://127.0.0.1:4747",
            "gnx_index_mode": block.get("gnx_index_mode") or "job",
            "code_intelligence_index_url": os.getenv("CODE_INTELLIGENCE_INDEX_URL")
            or block.get("code_intelligence_index_url")
            or "",
            "block_release_if_gnx_down": bool(block.get("block_release_if_gnx_down")),
        },
        "docs_only": applied["docs_only"],
    }
    return lc


def load_smoke_defaults() -> dict[str, Any]:
    return (_load_yaml("smoke-defaults.yaml").get("smoke_defaults") or {})
