"""Canonical import model + adapter protocol for external collections."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse


_VAR_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


@dataclass
class AmImportItem:
    api_id: str
    name: str
    method: str
    path: str
    path_params: dict[str, Any] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    auth_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_id": self.api_id,
            "name": self.name,
            "method": self.method,
            "path": self.path,
            "path_params": dict(self.path_params),
            "query": dict(self.query),
            "headers": dict(self.headers),
            "body": self.body,
            "auth_hint": self.auth_hint,
        }


@dataclass
class AmImportBundle:
    source: str
    service: str
    label: str
    env: dict[str, str] = field(default_factory=dict)
    items: list[AmImportItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "service": self.service,
            "label": self.label,
            "env": dict(self.env),
            "items": [i.to_dict() for i in self.items],
            "warnings": list(self.warnings),
        }


class CollectionAdapter(Protocol):
    format_id: str

    def detect(self, raw: Any) -> bool: ...

    def parse_collection(self, raw: Any, *, service: str) -> AmImportBundle: ...

    def parse_environment(self, raw: Any) -> dict[str, str]: ...


def substitute_vars(value: Any, env: dict[str, str]) -> Any:
    """Replace {{var}} placeholders using env map (string recursion)."""
    if isinstance(value, str):

        def repl(m: re.Match[str]) -> str:
            key = m.group(1).strip()
            if key in env:
                return str(env[key])
            # Postman baseUrl style
            if key.lower() in {k.lower(): k for k in env}:
                real = {k.lower(): k for k in env}[key.lower()]
                return str(env[real])
            return m.group(0)

        return _VAR_RE.sub(repl, value)
    if isinstance(value, list):
        return [substitute_vars(v, env) for v in value]
    if isinstance(value, dict):
        return {k: substitute_vars(v, env) for k, v in value.items()}
    return value


def normalize_request_path(path: str) -> str:
    """Drop scheme/host after env substitution so Try uses a relative path."""
    p = (path or "").strip()
    # Postman often yields `/{{base_url}}/health` → `/http://host/health` after sub.
    if p.startswith("/http://") or p.startswith("/https://"):
        p = p.lstrip("/")
    if p.startswith("http://") or p.startswith("https://"):
        parsed = urlparse(p)
        p = parsed.path or "/"
    # Bare {{base_url}}/… left unsubstituted
    if p.startswith("/{{") or p.startswith("{{"):
        p2 = p.lstrip("/")
        if p2.startswith("{{"):
            end = p2.find("}}")
            if end >= 0:
                rest = p2[end + 2 :]
                p = rest if rest.startswith("/") else (f"/{rest}" if rest else "/")
    if not p.startswith("/"):
        p = "/" + p
    while "//" in p:
        p = p.replace("//", "/")
    return p or "/"


def extract_path_params(path: str, env: dict[str, str]) -> tuple[str, dict[str, Any]]:
    """Turn `/x/{{id}}/y` into `/x/{id}/y` and fill path_params from env when present."""
    params: dict[str, Any] = {}

    def repl(m: re.Match[str]) -> str:
        key = m.group(1).strip()
        lower_map = {k.lower(): k for k in env}
        if key in env and str(env[key]).strip():
            params[key] = env[key]
        elif key.lower() in lower_map:
            real = lower_map[key.lower()]
            if str(env[real]).strip():
                params[key] = env[real]
        return "{" + key + "}"

    normalized = _VAR_RE.sub(repl, path)
    return normalized, params


def merge_bundle_env(bundle: AmImportBundle, env: dict[str, str] | None) -> AmImportBundle:
    merged_env = {**bundle.env, **(env or {})}
    # Host-only vars — substitute these before path-param extraction.
    host_keys = {
        k: v
        for k, v in merged_env.items()
        if k.lower() in {"base_url", "baseurl", "host", "api_base", "api_url"}
        and str(v).strip()
    }
    items: list[AmImportItem] = []
    for item in bundle.items:
        # 1) Expand host vars only → 2) strip scheme/host → 3) {{id}} → {id}
        path = str(substitute_vars(item.path, host_keys))
        path = normalize_request_path(path)
        path, extracted = extract_path_params(path, merged_env)
        path = normalize_request_path(path)
        path_params = {
            **(substitute_vars(item.path_params, merged_env) or {}),
            **extracted,
        }
        new_item = AmImportItem(
            api_id=substitute_vars(item.api_id, merged_env),
            name=substitute_vars(item.name, merged_env),
            method=item.method,
            path=path,
            path_params=path_params,
            query=substitute_vars(item.query, merged_env),
            headers=substitute_vars(item.headers, merged_env),
            body=substitute_vars(item.body, merged_env),
            auth_hint=item.auth_hint,
        )
        extra_meta = getattr(item, "extra_meta", None)
        if isinstance(extra_meta, dict):
            setattr(new_item, "extra_meta", substitute_vars(extra_meta, merged_env))
        extra_resp = getattr(item, "extra_response", None)
        if isinstance(extra_resp, dict):
            setattr(new_item, "extra_response", extra_resp)
        items.append(new_item)
    return AmImportBundle(
        source=bundle.source,
        service=bundle.service,
        label=bundle.label,
        env=merged_env,
        items=items,
        warnings=list(bundle.warnings),
    )


def slug_api_id(method: str, path: str, name: str = "") -> str:
    base = f"{method.lower()}.{(name or path).strip()}"
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", ".", base).strip(".")
    return (cleaned[:120] or "imported.request").lower()
