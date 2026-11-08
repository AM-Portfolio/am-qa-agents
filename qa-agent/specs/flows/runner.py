"""Stepped FLOW execution with per-node events + credential_id resolution."""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from specs import env_urls
from specs.flows.catalog import get_flow
from specs.flows.graph import MANUAL_TRIGGER_ID
from specs.flows import executions as ex_store
from specs.security.credential_store import resolve_credential

logger = logging.getLogger(__name__)


def _json_path_get(data: Any, expr: str) -> Any:
    """Tiny JSONPath subset: ``$.a.b``, ``$[0].id``, ``$.[0].symbol``."""
    import re

    e = (expr or "").strip()
    if not e:
        return None
    if e.startswith("$."):
        e = e[2:]
    elif e.startswith("$"):
        e = e[1:]
    e = e.lstrip(".")
    e = e.replace(".[", "[")
    if not e:
        return data
    cur: Any = data
    for part in re.findall(r"\[\d+\]|[^.\[\]]+", e):
        if part.startswith("[") and part.endswith("]"):
            try:
                idx = int(part[1:-1])
            except ValueError:
                return None
            if not isinstance(cur, list) or idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
    return cur


def _apply_captures(body: Any, capture: dict[str, Any] | None) -> dict[str, Any]:
    """Extract vars from a response body using capture map values as JSONPaths.

    Capture value may be a string path or a list of fallback paths.
    """
    if not isinstance(capture, dict) or not capture:
        return {}
    out: dict[str, Any] = {}
    for key, path in capture.items():
        if path is None:
            continue
        candidates = path if isinstance(path, list) else [path]
        for cand in candidates:
            val = _json_path_get(body, str(cand))
            if val is not None and str(val).strip() != "":
                out[str(key)] = val
                break
    return out


def _interpolate(value: Any, variables: dict[str, Any]) -> Any:
    """Replace ``{{var}}`` placeholders in strings (and nested dict/list)."""
    if isinstance(value, str):
        out = value
        for k, v in variables.items():
            if v is None:
                continue
            out = out.replace("{{" + str(k) + "}}", str(v))
        return out
    if isinstance(value, dict):
        return {str(k): _interpolate(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v, variables) for v in value]
    return value


def _seed_default_vars(
    *,
    services: list[str],
    environment: str,
    doc: dict[str, Any] | None,
    existing: dict[str, Any],
) -> dict[str, Any]:
    """Fill missing flow vars from payload-set env, then am-specs var_defaults."""
    out: dict[str, Any] = dict(existing or {})
    pin: int | None = None
    if isinstance(doc, dict) and doc.get("payload_set_version") is not None:
        try:
            pin = int(doc["payload_set_version"])
        except (TypeError, ValueError):
            pin = None
    for svc in services:
        sid = str(svc or "").strip()
        if not sid:
            continue
        try:
            from specs.payloads.payload_store import get_payload_set, list_payload_sets

            ver = pin
            if ver is None:
                active = list_payload_sets(sid).get("active_version")
                if active is not None:
                    ver = int(active)
            if ver is not None:
                ps = get_payload_set(sid, ver) or {}
                env_map = ps.get("env") if isinstance(ps.get("env"), dict) else {}
                for k, v in env_map.items():
                    if str(k) not in out and v is not None and v != "":
                        out[str(k)] = v
        except Exception as exc:  # noqa: BLE001
            logger.debug("payload env seed skipped for %s: %s", sid, exc)
        try:
            from specs.data_gen.pack import load_var_defaults

            for k, v in load_var_defaults(sid, environment).items():
                if str(k) not in out and v is not None and v != "":
                    out[str(k)] = v
        except Exception as exc:  # noqa: BLE001
            logger.debug("var_defaults seed skipped for %s: %s", sid, exc)
    return out


def _identity_login(
    *,
    identity_base: str,
    user: str,
    password: str,
) -> str | None:
    """POST identity /auth/login; return access_token or None."""
    if not identity_base or not user or not password:
        return None
    import httpx

    url = f"{str(identity_base).rstrip('/')}/auth/login"
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                url,
                json={"username": user, "password": password},
                headers={
                    "Accept": "application/json",
                    "User-Agent": "am-qa-flows/1.0",
                },
            )
        if not resp.is_success:
            logger.warning("flow auto-login failed %s: %s", resp.status_code, resp.text[:200])
            return None
        body = resp.json() if resp.content else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("flow auto-login error: %s", exc)
        return None
    if not isinstance(body, dict):
        return None
    token = body.get("access_token") or (body.get("data") or {}).get("access_token")
    return str(token) if token else None


def _apply_bindings(
    node: dict[str, Any],
    args: dict[str, Any],
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Apply bind_query / bind_path / templated path_params onto args.

    Unresolved ``{{var}}`` values do not overwrite payload-set defaults.
    """
    out = dict(args)
    for block_key in ("bind_query", "bind_path", "path_params", "query_override"):
        block = node.get(block_key)
        if not isinstance(block, dict):
            continue
        for k, v in block.items():
            rendered = _interpolate(v, variables)
            if isinstance(rendered, str) and "{{" in rendered and "}}" in rendered:
                # Keep existing arg (e.g. payload-set symbol) when capture missed.
                if str(k) in out and out[str(k)] is not None:
                    continue
            out[str(k)] = rendered
    # Interpolate leftover templates in existing args (payload {{watchlistId}} etc.).
    cleaned: dict[str, Any] = {}
    for k, v in out.items():
        rendered = _interpolate(v, variables)
        if isinstance(rendered, str) and "{{" in rendered and "}}" in rendered:
            continue
        cleaned[str(k)] = rendered
    return cleaned


def _merge_body_override(
    args: dict[str, Any],
    body_override: Any,
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Merge body_override after interpolating nested ``{{vars}}``."""
    if not isinstance(body_override, dict):
        return args
    rendered = _interpolate(body_override, variables)
    if not isinstance(rendered, dict):
        return args
    return {**args, **rendered}


def _node_http_hints(node: dict[str, Any]) -> tuple[str, str]:
    method = str(node.get("method") or "get").upper()
    path = str(
        node.get("exact_path")
        or node.get("path")
        or node.get("path_contains")
        or ""
    ).rstrip("/") or "/"
    return method, path


def _pick_payload_entry(
    apis: dict[str, Any],
    *,
    api_id: str,
    method: str,
    path: str,
    name: str,
) -> dict[str, Any] | None:
    entry: dict[str, Any] | None = None
    if api_id and isinstance(apis.get(api_id), dict):
        entry = apis[api_id]
    if entry is None:
        method_u = (method or "").upper()
        path_s = (path or "").rstrip("/") or "/"
        for cand in apis.values():
            if not isinstance(cand, dict):
                continue
            req = cand.get("request") if isinstance(cand.get("request"), dict) else {}
            if not isinstance(req, dict):
                # Nested variant bag: try named / first request-bearing child
                named = cand.get(name) if name else None
                if isinstance(named, dict) and isinstance(named.get("request"), dict):
                    req = named["request"]
                else:
                    continue
            if str(req.get("method") or "").upper() != method_u:
                continue
            if (str(req.get("path") or "").rstrip("/") or "/") != path_s:
                continue
            entry = cand
            break
    if not isinstance(entry, dict):
        return None
    if isinstance(entry.get(name), dict):
        entry = entry[name]
    elif entry.get("name") and str(entry.get("name")) != name and "request" not in entry:
        named = entry.get(name)
        if isinstance(named, dict):
            entry = named
    return entry if isinstance(entry, dict) else None


def _merge_payload_set_into_args(
    node: dict[str, Any],
    args: dict[str, Any],
    *,
    doc: dict[str, Any] | None = None,
    payload_set_version: int | None = None,
) -> dict[str, Any]:
    """Apply payload-set request body/query/path_params onto tool args when bound.

    Resolves by ``payload_api_id`` when set; otherwise matches method+path so
    authored FLOW_* graphs still pick up data-gen prod/full/premium datasets.
    """
    svc = str(node.get("service") or "").strip()
    if not svc:
        return args
    api_id = str(node.get("payload_api_id") or "").strip()
    method, path = _node_http_hints(node)
    if not api_id and path in {"", "/"}:
        return args
    name = str(node.get("payload_name") or "must_work").strip() or "must_work"
    ver = payload_set_version
    if ver is None and isinstance(doc, dict) and doc.get("payload_set_version") is not None:
        try:
            ver = int(doc.get("payload_set_version"))
        except (TypeError, ValueError):
            ver = None
    try:
        from specs.payloads.payload_store import get_payload_set, list_payload_sets

        if ver is None:
            meta = list_payload_sets(svc)
            active = meta.get("active_version")
            if active is not None:
                ver = int(active)
        ps = get_payload_set(svc, ver)
    except Exception as exc:
        logger.info("payload set load skipped for %s/%s: %s", svc, api_id or path, exc)
        return args
    if not ps or not isinstance(ps.get("apis"), dict):
        return args
    entry = _pick_payload_entry(
        ps["apis"], api_id=api_id, method=method, path=path, name=name
    )
    if entry is None:
        return args
    req = entry.get("request") if isinstance(entry.get("request"), dict) else entry
    if not isinstance(req, dict):
        return args
    out = dict(args)
    body = req.get("body")
    if isinstance(body, dict):
        out = {**out, **body}
    elif body is not None and "body" not in out:
        out["body"] = body
    query = req.get("query")
    if isinstance(query, dict):
        for qk, qv in query.items():
            if qv is not None and str(qk) not in out:
                out[str(qk)] = qv
    path_params = req.get("path_params")
    if isinstance(path_params, dict):
        for pk, pv in path_params.items():
            if pv is not None and str(pk) not in out:
                out[str(pk)] = pv
    return out


def _fill_path_template(path: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Replace ``{param}`` segments from args; return (path, leftover_args)."""
    import re

    leftover = dict(args)
    out = str(path or "")

    def _repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in leftover and leftover[key] is not None:
            val = leftover.pop(key)
            return str(val)
        # also accept path_params nested
        return match.group(0)

    out = re.sub(r"\{([^{}/]+)\}", _repl, out)
    return out, leftover


def _raw_http_call(
    *,
    base: str,
    method: str,
    path: str,
    headers: dict[str, str],
    args: dict[str, Any],
) -> dict[str, Any]:
    """HTTP call that applies path params + JSON/query from payload args."""
    import httpx

    p = str(path or "")
    if not p.startswith("/"):
        p = "/" + p
    filled, leftover = _fill_path_template(p, args)
    # Prefer explicit body key; else treat leftover as JSON body for write methods.
    json_body: Any = None
    params: dict[str, Any] | None = None
    if "body" in leftover:
        json_body = leftover.pop("body")
    method_u = (method or "get").upper()
    if method_u in {"GET", "HEAD", "DELETE"}:
        params = {k: v for k, v in leftover.items() if v is not None} or None
    else:
        if json_body is None and leftover:
            json_body = leftover
        elif leftover and isinstance(json_body, dict):
            json_body = {**leftover, **json_body}
    url = f"{base.rstrip('/')}{filled}"
    with httpx.Client(timeout=45.0) as client:
        resp = client.request(
            method_u,
            url,
            headers=headers,
            params=params,
            json=json_body if json_body is not None else None,
        )
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"raw": resp.text[:500]}
    return {
        "ok": 200 <= resp.status_code < 300,
        "status": resp.status_code,
        "url": str(resp.request.url),
        "body": body,
        "error": None if resp.is_success else body,
        "path": filled,
        "request_body": json_body,
        "request_params": params,
    }


def _redact_body(body: Any) -> Any:
    if isinstance(body, dict):
        out = {}
        for k, v in body.items():
            lk = str(k).lower()
            if any(x in lk for x in ("password", "token", "secret", "authorization")):
                out[k] = "<redacted>"
            else:
                out[k] = _redact_body(v)
        return out
    if isinstance(body, list):
        return [_redact_body(x) for x in body[:40]]
    return body


def _redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Copy headers with Authorization / cookie secrets redacted."""
    out: dict[str, str] = {}
    for k, v in (headers or {}).items():
        lk = str(k).lower()
        if lk in {"authorization", "cookie", "set-cookie", "x-api-key"}:
            if lk == "authorization" and str(v).lower().startswith("bearer "):
                out[k] = "Bearer <redacted>"
            else:
                out[k] = "<redacted>"
        else:
            out[k] = str(v)
    return out


def _request_envelope(
    *,
    method: str,
    url: Any,
    path: Any,
    headers: dict[str, str] | None,
    body: Any,
) -> dict[str, Any]:
    # Headers use their own redactor so Authorization stays "Bearer <redacted>".
    return {
        "method": (method or "GET").upper(),
        "url": url,
        "path": path,
        "headers": _redact_headers(headers),
        "body": _redact_body(body) if body else None,
    }


def _creds_for_run(
    *,
    credential_id: str | None,
    env: str,
) -> tuple[str, str, str, str, str]:
    """Return username, password, identity_url, gateway_host, effective_env.

    Execute ``env`` picks the product surface (identity + subscriptions stay
    paired). Credential supplies username/password only — never a cross-env
    identity base (dig JWT against prod /me → 500).
    """
    eff = env_urls.normalize_env(env) or "prod"
    identity = env_urls.identity_url_for_env(eff).rstrip("/")
    gateway = env_urls.public_host(eff).rstrip("/")
    if credential_id:
        rec = resolve_credential(credential_id)
        if not rec:
            raise ValueError(f"credential not found: {credential_id}")
        user = str(rec.get("username") or "")
        password = str(rec.get("password") or "")
        return user, password, identity, gateway, eff
    user = (
        os.environ.get("SPT_AUTH_USERNAME")
        or os.environ.get("ASRAX_PROD_EMAIL")
        or os.environ.get("ASRAX_DEV_EMAIL")
        or ""
    ).strip()
    password = (
        os.environ.get("SPT_AUTH_PASSWORD")
        or os.environ.get("ASRAX_PROD_PASSWORD")
        or os.environ.get("ASRAX_DEV_PASSWORD")
        or ""
    )
    return user, password, identity, gateway, eff


def _service_base_url(
    service: str,
    *,
    env: str,
    identity_base: str,
    gateway_host: str,
    base_url_override: str | None = None,
) -> str:
    """Resolve HTTP base for a flow node.

    Identity stays on the auth surface; subscription uses the public gateway;
    every other service uses the catalog target for ``env`` (e.g. dig market →
    ``https://am-dev.asrax.in/market``). Never default non-identity APIs to
    ``identity_base`` — that yields 404s like ``/identity/v1/watchlists``.
    """
    if base_url_override:
        return str(base_url_override).rstrip("/")
    svc = (service or "").strip().lower()
    if not svc or "identity" in svc:
        return identity_base.rstrip("/")
    if "subscription" in svc:
        return gateway_host.rstrip("/")
    try:
        from specs.catalog.catalog_loader import default_target_for_service

        target = default_target_for_service(svc, env)
        if target and str(target).startswith("http"):
            return str(target).rstrip("/")
    except Exception:  # noqa: BLE001
        logger.debug("catalog target resolve failed for %s/%s", svc, env, exc_info=True)
    return gateway_host.rstrip("/")


def _subscription_request(
    *,
    host: str,
    step_id: str,
    label: str,
    path_hint: str,
    method: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    """Hit public gateway subscription routes; health falls back when /health 404."""
    import httpx

    sid_l = step_id.lower()
    label_l = (label or "").lower()
    hint = f"{path_hint} {sid_l} {label_l}".lower()
    host = host.rstrip("/")

    if "health" in hint:
        # Prod gateway has no /subscriptions/health (404). Dig may 401/503.
        # Probe /health first; on 404 use /plans as gateway liveness.
        candidates = [
            (f"{host}/subscriptions/health", "/subscriptions/health"),
            (f"{host}/subscriptions/plans", "/subscriptions/plans"),
        ]
        last: dict[str, Any] | None = None
        with httpx.Client(timeout=45.0) as client:
            for url, path in candidates:
                resp = client.request(method.upper(), url, headers=headers)
                try:
                    body = resp.json()
                except Exception:  # noqa: BLE001
                    body = {"raw": resp.text[:500]}
                last = {
                    "ok": 200 <= resp.status_code < 300,
                    "status": resp.status_code,
                    "url": url,
                    "body": body,
                    "error": None if resp.is_success else body,
                    "path": path,
                }
                if resp.is_success:
                    return last
                if resp.status_code != 404:
                    return last
        return last or {
            "ok": False,
            "status": 0,
            "url": candidates[0][0],
            "body": {},
            "error": "health probe failed",
            "path": "/subscriptions/health",
        }

    if "plan" in hint:
        url = f"{host}/subscriptions/plans"
        path = "/subscriptions/plans"
    elif "me" in hint or "current" in hint:
        url = f"{host}/subscriptions/me"
        path = "/subscriptions/me"
    else:
        p = str(path_hint or "/").strip()
        if not p.startswith("/"):
            p = "/" + p
        url = (
            f"{host}/subscriptions{p}"
            if "/subscriptions" not in p
            else f"{host}{p}"
        )
        path = p

    with httpx.Client(timeout=45.0) as client:
        resp = client.request(method.upper(), url, headers=headers)
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"raw": resp.text[:500]}
    return {
        "ok": 200 <= resp.status_code < 300,
        "status": resp.status_code,
        "url": url,
        "body": body,
        "error": None if resp.is_success else body,
        "path": path,
    }


def _topo_order(doc: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = {n["id"]: n for n in (doc.get("nodes") or [])}
    edges = list(doc.get("edges") or [])
    indeg = {nid: 0 for nid in nodes}
    succ: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        frm, to = e["from"], e["to"]
        if frm in nodes and to in nodes:
            succ[frm].append(to)
            indeg[to] = indeg.get(to, 0) + 1
    queue = [nid for nid, d in indeg.items() if d == 0]
    # Stable: preserve document order among zeros
    order_index = {n["id"]: i for i, n in enumerate(doc.get("nodes") or [])}
    queue.sort(key=lambda x: order_index.get(x, 0))
    out: list[str] = []
    while queue:
        queue.sort(key=lambda x: order_index.get(x, 0))
        nid = queue.pop(0)
        out.append(nid)
        for nxt in succ.get(nid) or []:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(out) != len(nodes):
        # cycle fallback: document order
        return list(doc.get("nodes") or [])
    return [nodes[nid] for nid in out]


def _run_sync(execution_id: str) -> None:
    row = ex_store.get_execution(execution_id)
    if not row:
        return
    flow_id = str(row["flow_id"])
    env = str(row.get("env") or "prod")
    credential_id = row.get("credential_id")
    doc = get_flow(flow_id)
    if not doc:
        ex_store.set_error(execution_id, f"flow not found: {flow_id}")
        return
    raw = ex_store.get_execution(execution_id, include_raw=True) or row
    run_vars = (
        raw.get("_variables_raw")
        if isinstance(raw.get("_variables_raw"), dict)
        else {}
    )
    doc_vars = doc.get("variables") if isinstance(doc.get("variables"), dict) else {}
    merged_vars = {**doc_vars, **run_vars}
    ordered = _topo_order(doc)
    services = sorted(
        {
            str(n.get("service"))
            for n in ordered
            if n.get("service")
        }
    )
    merged_vars = _seed_default_vars(
        services=services,
        environment=env,
        doc=doc if isinstance(doc, dict) else None,
        existing=merged_vars,
    )

    ex_store.append_event(
        execution_id,
        {
            "type": "execution_started",
            "flow_id": flow_id,
            "env": env,
            "payload_set_version": row.get("payload_set_version"),
            "suite_run_id": row.get("suite_run_id"),
            "variables": row.get("variables") or {},
        },
    )

    try:
        user, password, identity_base, gateway_host, eff_env = _creds_for_run(
            credential_id=credential_id or doc.get("credential_id"),
            env=env,
        )
    except Exception as exc:  # noqa: BLE001
        ex_store.set_error(execution_id, str(exc))
        return

    access_token: str | None = None
    failures: list[str] = []
    passed = 0

    # Lazy imports — OpenAPI tools need app path
    try:
        from specs.openapi_tools.generator import execute_openapi_tool_sync
        from specs.openapi_tools.registry import list_tools
        from ui_evidence.api.run_auth_user_api_flows import (
            _resolve_tool,
            _tool_meta,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("flow runner imports failed")
        ex_store.set_error(execution_id, f"runner import failed: {exc}")
        return
    tools_by_svc: dict[str, list[dict[str, Any]]] = {}
    for svc in services:
        try:
            tools_by_svc[svc] = list(
                list_tools(service=svc, limit=1000).get("tools") or []
            )
        except Exception:  # noqa: BLE001
            tools_by_svc[svc] = []

    # Keep login + API on the same surface (execute env), not OpenAPI cluster DNS.
    id_base = identity_base

    # Graph-only Manual Trigger — emit ok so the portal start node lights up.
    ex_store.append_event(
        execution_id,
        {
            "type": "node_started",
            "node_id": MANUAL_TRIGGER_ID,
            "label": "Manual Trigger",
            "service": None,
            "method": "START",
        },
    )
    ex_store.append_event(
        execution_id,
        {
            "type": "node_finished",
            "node_id": MANUAL_TRIGGER_ID,
            "status": "ok",
            "http_status": None,
            "duration_ms": 0,
            "label": "Manual Trigger",
        },
    )
    passed += 1

    for node in ordered:
        if ex_store.stop_requested(execution_id):
            ex_store.append_event(
                execution_id,
                {
                    "type": "execution_finished",
                    "status": "stopped",
                    "summary": {"ok": False, "failures": failures, "passed": passed},
                },
            )
            return

        nid = str(node["id"])
        # Strip pack prefix for display in OpenAPI resolve (FLOW_X::step)
        step_id = nid.split("::")[-1]
        step = dict(node)
        step["id"] = step_id
        kind = str(node.get("kind") or "call_tool")

        ex_store.append_event(
            execution_id,
            {
                "type": "node_started",
                "node_id": nid,
                "label": node.get("label") or step_id,
                "service": node.get("service"),
                "method": node.get("method"),
            },
        )
        t0 = time.perf_counter()
        optional = bool(node.get("optional"))

        # Graph-only start node — always succeeds (UI click / Run starts the flow).
        if kind == "manual_trigger" or nid == MANUAL_TRIGGER_ID:
            passed += 1
            ex_store.append_event(
                execution_id,
                {
                    "type": "node_finished",
                    "node_id": nid,
                    "status": "ok",
                    "http_status": None,
                    "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "label": "Manual Trigger",
                },
            )
            continue

        svc = str(node.get("service") or "")
        tools = tools_by_svc.get(svc) or []
        tool = _resolve_tool(tools, step)

        try:
            node_cred = node.get("credential_id") or credential_id or doc.get(
                "credential_id"
            )
            if node_cred and node_cred != credential_id:
                user, password, identity_base, gateway_host, eff_env = _creds_for_run(
                    credential_id=str(node_cred), env=env
                )
                id_base = identity_base

            args: dict[str, Any] = {}
            if node.get("uses_spt_auth_creds") or (
                kind == "call_tool"
                and "login" in step_id.lower()
                and svc.endswith("identity")
            ):
                args = {"username": user, "password": password}
            # Creds only here — other vars feed next hops via capture/bind {{}}.
            for vk, vv in merged_vars.items():
                if vv == "<redacted>":
                    continue
                if str(vk).lower() in {"username", "password", "email"}:
                    args[str(vk).lower() if str(vk).lower() != "email" else "username"] = vv
                    if str(vk).lower() == "username" or str(vk).lower() == "email":
                        user = str(vv)
                    if str(vk).lower() == "password":
                        password = str(vv)
            pin_ver = row.get("payload_set_version")
            try:
                pin_ver_i = int(pin_ver) if pin_ver is not None else None
            except (TypeError, ValueError):
                pin_ver_i = None
            args = _merge_payload_set_into_args(
                node, args, doc=doc, payload_set_version=pin_ver_i
            )
            body_override = node.get("body_override")
            args = _merge_body_override(args, body_override, merged_vars)
            # bind_query / bind_path / path_params win over payload defaults so
            # chained captures (watchlist → LTP) actually feed the next hop.
            args = _apply_bindings(node, args, merged_vars)

            # dg_* graphs mark auth=true without a login node — acquire Bearer once.
            if (
                node.get("auth")
                and not access_token
                and not _is_login_node(node, step_id)
                and user
                and password
            ):
                access_token = _identity_login(
                    identity_base=id_base or identity_base,
                    user=user,
                    password=password,
                )
                if access_token:
                    ex_store.append_event(
                        execution_id,
                        {
                            "type": "auto_login",
                            "status": "ok",
                            "service": "am-identity",
                            "label": "SPT auto-login",
                        },
                    )

            headers = {"Accept": "application/json", "User-Agent": "am-qa-flows/1.0"}
            if node.get("auth") and access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            # Non-secret header overrides from variables (header:X / headers.X)
            for vk, vv in merged_vars.items():
                if vv == "<redacted>":
                    continue
                sk = str(vk)
                if sk.lower().startswith("header:"):
                    headers[sk.split(":", 1)[1].strip()] = str(vv)
                elif sk.lower().startswith("headers."):
                    headers[sk.split(".", 1)[1].strip()] = str(vv)
            node_headers = node.get("headers")
            if isinstance(node_headers, dict):
                for hk, hv in node_headers.items():
                    if hv is None:
                        continue
                    headers[str(hk)] = str(_interpolate(hv, merged_vars))

            method = str(
                (tool or {}).get("method") or node.get("method") or "get"
            ).lower()
            base = _service_base_url(
                svc,
                env=eff_env,
                identity_base=id_base,
                gateway_host=gateway_host,
                base_url_override=(
                    str(node["base_url_override"])
                    if node.get("base_url_override")
                    else None
                ),
            )
            meta = _tool_meta(tool, svc=svc, step=step, base=base)

            # Prefer raw HTTP when we have path hints (more reliable for login)
            path = (
                node.get("exact_path")
                or node.get("path")
                or (tool or {}).get("path")
                or node.get("path_contains")
                or ""
            )
            path = str(_interpolate(path, merged_vars))
            import httpx

            is_login = bool(
                node.get("uses_spt_auth_creds")
                or (
                    "login" in step_id.lower()
                    and svc.find("identity") >= 0
                )
                or (isinstance(body_override, dict) and "password" in body_override
                    and svc.find("identity") >= 0)
            )
            if is_login and (
                node.get("uses_spt_auth_creds")
                or "login" in step_id.lower()
                or isinstance(body_override, dict)
            ):
                url = f"{identity_base}/auth/login"
                login_body = args or {"username": user, "password": password}
                with httpx.Client(timeout=45.0) as client:
                    resp = client.post(
                        url,
                        json=login_body,
                        headers=headers,
                    )
                body = {}
                try:
                    body = resp.json()
                except Exception:  # noqa: BLE001
                    body = {"raw": resp.text[:500]}
                out = {
                    "ok": 200 <= resp.status_code < 300,
                    "status": resp.status_code,
                    "url": url,
                    "body": body,
                    "error": None if resp.is_success else body,
                }
                method = "post"
                path = "/auth/login"
            elif "subscription" in svc:
                out = _subscription_request(
                    host=gateway_host,
                    step_id=step_id,
                    label=str(node.get("label") or ""),
                    path_hint=str(path or ""),
                    method=method,
                    headers=headers,
                )
                path = str(out.get("path") or path)
            elif kind == "raw_http" or not tool:
                if not path:
                    raise ValueError("no path/tool for node")
                out = _raw_http_call(
                    base=base,
                    method=method,
                    path=str(path),
                    headers=headers,
                    args=args,
                )
                path = str(out.get("path") or path)
            else:
                out = execute_openapi_tool_sync(dict(meta), args, headers=headers)
                path = meta.get("path") or path

            http = int(out.get("status") or 0)
            expect = node.get("expect_status")
            if isinstance(expect, list) and expect:
                ok = http in {int(x) for x in expect}
            else:
                ok = bool(out.get("ok"))
            body = out.get("body")
            if node.get("capture_tokens") and ok and isinstance(body, dict):
                access_token = (
                    body.get("access_token")
                    or (body.get("data") or {}).get("access_token")
                    or access_token
                )

            captured: dict[str, Any] = {}
            if ok:
                status = "ok"
                passed += 1
                captured = _apply_captures(body, node.get("capture"))
                if captured:
                    merged_vars.update(captured)
            elif optional:
                status = "skipped"
            else:
                status = "fail"
                failures.append(nid)

            dur = round((time.perf_counter() - t0) * 1000, 1)
            ex_store.append_event(
                execution_id,
                {
                    "type": "node_finished",
                    "node_id": nid,
                    "status": status,
                    "http_status": http,
                    "duration_ms": dur,
                    "url": out.get("url"),
                    "method": method.upper(),
                    "path": path,
                    "request": _request_envelope(
                        method=method,
                        url=out.get("url"),
                        path=path,
                        headers=headers,
                        body=args or None,
                    ),
                    "response": _redact_body(body),
                    "error": _redact_body(out.get("error")) if not ok else None,
                    "captured": captured or None,
                },
            )
        except Exception as exc:  # noqa: BLE001
            dur = round((time.perf_counter() - t0) * 1000, 1)
            if optional:
                status = "skipped"
            else:
                status = "fail"
                failures.append(nid)
            # Surface intended request even on timeout so operators see data feed.
            req_env = None
            try:
                req_env = _request_envelope(
                    method=locals().get("method") or node.get("method") or "get",
                    url=None,
                    path=locals().get("path") or node.get("path") or node.get("exact_path"),
                    headers=locals().get("headers"),
                    body=locals().get("args") or None,
                )
            except Exception:  # noqa: BLE001
                req_env = None
            ex_store.append_event(
                execution_id,
                {
                    "type": "node_finished",
                    "node_id": nid,
                    "status": status,
                    "http_status": None,
                    "duration_ms": dur,
                    "path": locals().get("path") or node.get("path"),
                    "method": str(
                        (locals().get("method") or node.get("method") or "get")
                    ).upper(),
                    "request": req_env,
                    "error": str(exc),
                },
            )

    # Extract me_plan if present
    me_plan = None
    me_plan_name = None
    plans_count = 0
    for ev in (ex_store.get_execution(execution_id) or {}).get("events") or []:
        if ev.get("type") != "node_finished":
            continue
        nid = str(ev.get("node_id") or "")
        resp = ev.get("response")
        if not isinstance(resp, dict):
            continue
        data = resp.get("data", resp)
        if "me" in nid.lower() and isinstance(data, dict):
            me_plan = data.get("plan_code") or data.get("planCode") or me_plan
            me_plan_name = data.get("plan_name") or data.get("planName") or me_plan_name
        if "plan" in nid.lower():
            plans = data if isinstance(data, list) else (
                data.get("data") if isinstance(data, dict) else None
            )
            if isinstance(plans, list):
                plans_count = len(plans)

    summary = {
        "ok": len(failures) == 0,
        "failures": failures,
        "passed": passed,
        "me_plan": me_plan,
        "me_plan_name": me_plan_name,
        "plans_count": plans_count,
    }
    ex_store.append_event(
        execution_id,
        {
            "type": "execution_finished",
            "status": "finished" if summary["ok"] else "failed",
            "summary": summary,
        },
    )


def _find_node(doc: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    nid = (node_id or "").strip()
    for n in doc.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        if str(n.get("id") or "") == nid:
            return n
        # Pack-prefixed ids: FLOW_X::step
        if nid.endswith("::" + str(n.get("id") or "")):
            return n
        if str(n.get("id") or "").endswith("::" + nid) or str(n.get("id") or "").split("::")[-1] == nid:
            return n
    return None


def _is_login_node(node: dict[str, Any], step_id: str) -> bool:
    svc = str(node.get("service") or "")
    body_override = node.get("body_override")
    return bool(
        node.get("uses_spt_auth_creds")
        or ("login" in step_id.lower() and "identity" in svc)
        or (
            isinstance(body_override, dict)
            and "password" in body_override
            and "identity" in svc
        )
    )


def _invoke_single_node(
    node: dict[str, Any],
    *,
    user: str,
    password: str,
    identity_base: str,
    gateway_host: str,
    access_token: str | None,
    merged_vars: dict[str, Any],
    tools: list[dict[str, Any]],
    env: str = "dev",
    doc: dict[str, Any] | None = None,
    payload_set_version: int | None = None,
) -> dict[str, Any]:
    """Execute one flow node; return ok/status/request/response (redacted)."""
    from specs.openapi_tools.generator import execute_openapi_tool_sync
    from ui_evidence.api.run_auth_user_api_flows import _resolve_tool, _tool_meta
    import httpx

    nid = str(node.get("id") or "")
    step_id = nid.split("::")[-1]
    step = dict(node)
    step["id"] = step_id
    kind = str(node.get("kind") or "call_tool")
    svc = str(node.get("service") or "")
    tool = _resolve_tool(tools, step)

    args: dict[str, Any] = {}
    if node.get("uses_spt_auth_creds") or (
        kind == "call_tool" and "login" in step_id.lower() and svc.endswith("identity")
    ):
        args = {"username": user, "password": password}
    for vk, vv in merged_vars.items():
        if vv == "<redacted>":
            continue
        if str(vk).lower() in {"username", "password", "email"}:
            key = "username" if str(vk).lower() == "email" else str(vk).lower()
            args[key] = vv
            if key == "username":
                user = str(vv)
            if key == "password":
                password = str(vv)
    args = _merge_payload_set_into_args(
        node, args, doc=doc, payload_set_version=payload_set_version
    )
    body_override = node.get("body_override")
    args = _merge_body_override(args, body_override, merged_vars)
    args = _apply_bindings(node, args, merged_vars)

    token = access_token
    if (
        node.get("auth")
        and not token
        and not _is_login_node(node, step_id)
        and user
        and password
    ):
        token = _identity_login(
            identity_base=identity_base, user=user, password=password
        )

    headers = {"Accept": "application/json", "User-Agent": "am-qa-flows/1.0"}
    if node.get("auth") and token:
        headers["Authorization"] = f"Bearer {token}"
    for vk, vv in merged_vars.items():
        if vv == "<redacted>":
            continue
        sk = str(vk)
        if sk.lower().startswith("header:"):
            headers[sk.split(":", 1)[1].strip()] = str(vv)
        elif sk.lower().startswith("headers."):
            headers[sk.split(".", 1)[1].strip()] = str(vv)
    node_headers = node.get("headers")
    if isinstance(node_headers, dict):
        for hk, hv in node_headers.items():
            if hv is None:
                continue
            headers[str(hk)] = str(_interpolate(hv, merged_vars))

    method = str((tool or {}).get("method") or node.get("method") or "get").lower()
    id_base = identity_base
    base = _service_base_url(
        svc,
        env=env,
        identity_base=id_base,
        gateway_host=gateway_host,
        base_url_override=(
            str(node["base_url_override"]) if node.get("base_url_override") else None
        ),
    )
    meta = _tool_meta(tool, svc=svc, step=step, base=base)
    path = (
        node.get("exact_path")
        or node.get("path")
        or (tool or {}).get("path")
        or node.get("path_contains")
        or ""
    )
    path = str(_interpolate(path, merged_vars))

    t0 = time.perf_counter()
    try:
        if _is_login_node(node, step_id) and (
            node.get("uses_spt_auth_creds")
            or "login" in step_id.lower()
            or isinstance(body_override, dict)
        ):
            url = f"{identity_base}/auth/login"
            login_body = args or {"username": user, "password": password}
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(url, json=login_body, headers=headers)
            try:
                body = resp.json()
            except Exception:  # noqa: BLE001
                body = {"raw": resp.text[:500]}
            out = {
                "ok": 200 <= resp.status_code < 300,
                "status": resp.status_code,
                "url": url,
                "body": body,
                "error": None if resp.is_success else body,
            }
            method = "post"
            path = "/auth/login"
        elif "subscription" in svc:
            out = _subscription_request(
                host=gateway_host,
                step_id=step_id,
                label=str(node.get("label") or ""),
                path_hint=str(path or ""),
                method=method,
                headers=headers,
            )
            path = str(out.get("path") or path)
        elif kind == "raw_http" or not tool:
            if not path:
                raise ValueError("no path/tool for node")
            out = _raw_http_call(
                base=base,
                method=method,
                path=str(path),
                headers=headers,
                args=args,
            )
            path = str(out.get("path") or path)
        else:
            out = execute_openapi_tool_sync(dict(meta), args, headers=headers)
            path = meta.get("path") or path

        http = int(out.get("status") or 0)
        expect = node.get("expect_status")
        if isinstance(expect, list) and expect:
            ok = http in {int(x) for x in expect}
        else:
            ok = bool(out.get("ok"))
        body = out.get("body")
        token_out = token
        if node.get("capture_tokens") and ok and isinstance(body, dict):
            captured_tok = body.get("access_token") or (body.get("data") or {}).get(
                "access_token"
            )
            if captured_tok:
                token_out = captured_tok
        dur = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "ok": ok,
            "status": "ok" if ok else "fail",
            "http_status": http,
            "duration_ms": dur,
            "access_token": token_out,
            "request": _request_envelope(
                method=method,
                url=out.get("url"),
                path=path,
                headers=headers,
                body=args or None,
            ),
            "response": _redact_body(body),
            "error": _redact_body(out.get("error")) if not ok else None,
            "method": method.upper(),
            "path": path,
            "url": out.get("url"),
        }
    except Exception as exc:  # noqa: BLE001
        dur = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "ok": False,
            "status": "fail",
            "http_status": None,
            "duration_ms": dur,
            "access_token": None,
            "request": _request_envelope(
                method=method,
                url=None,
                path=path,
                headers=headers,
                body=args or None,
            ),
            "response": None,
            "error": str(exc),
            "method": method.upper(),
            "path": path,
            "url": None,
        }


def quick_test_node(
    flow_id: str,
    node_id: str,
    *,
    env: str = "prod",
    credential_id: str | None = None,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a single node (optionally login first if auth required). No execution store."""
    env_n = (env or "prod").strip().lower()
    if env_n == "dig":
        env_n = "dev"
    doc = get_flow(flow_id)
    if not doc:
        raise ValueError(f"flow not found: {flow_id}")
    node = _find_node(doc, node_id)
    if not node:
        raise ValueError(f"node not found: {node_id}")
    kind = str(node.get("kind") or "call_tool")
    if kind == "manual_trigger" or str(node.get("id")) == MANUAL_TRIGGER_ID:
        return {
            "ok": True,
            "status": "ok",
            "http_status": None,
            "duration_ms": 0,
            "request": None,
            "response": {"note": "Manual Trigger — use Run for full flow"},
            "error": None,
            "node_id": node_id,
            "flow_id": flow_id,
            "env": env_n,
        }

    doc_vars = doc.get("variables") if isinstance(doc.get("variables"), dict) else {}
    merged_vars = {**doc_vars, **(variables or {})}
    svc_hint = str(node.get("service") or doc.get("api_pack") or "").strip()
    seed_svcs = [svc_hint] if svc_hint else []
    for n in doc.get("nodes") or []:
        if isinstance(n, dict) and n.get("service"):
            s = str(n["service"])
            if s not in seed_svcs:
                seed_svcs.append(s)
    merged_vars = _seed_default_vars(
        services=seed_svcs,
        environment=env_n,
        doc=doc if isinstance(doc, dict) else None,
        existing=merged_vars,
    )
    user, password, identity_base, gateway_host, eff_env = _creds_for_run(
        credential_id=credential_id or doc.get("credential_id"),
        env=env_n,
    )

    from specs.openapi_tools.registry import list_tools

    access_token: str | None = None
    # Prefetch login if target needs auth
    if node.get("auth") and not node.get("uses_spt_auth_creds"):
        login_node = None
        for n in doc.get("nodes") or []:
            if not isinstance(n, dict):
                continue
            sid = str(n.get("id") or "").split("::")[-1]
            if _is_login_node(n, sid) or n.get("capture_tokens"):
                login_node = n
                break
        if login_node is not None and str(login_node.get("id")) != str(node.get("id")):
            svc_l = str(login_node.get("service") or "")
            tools_l = list(list_tools(service=svc_l, limit=1000).get("tools") or []) if svc_l else []
            login_out = _invoke_single_node(
                login_node,
                user=user,
                password=password,
                identity_base=identity_base,
                gateway_host=gateway_host,
                access_token=None,
                merged_vars=merged_vars,
                tools=tools_l,
                env=eff_env,
                doc=doc,
                payload_set_version=(
                    int(doc["payload_set_version"])
                    if doc.get("payload_set_version") is not None
                    else None
                ),
            )
            if login_out.get("access_token"):
                access_token = str(login_out["access_token"])
            elif not login_out.get("ok"):
                return {
                    **login_out,
                    "ok": False,
                    "error": {
                        "message": "login prerequisite failed",
                        "login": login_out.get("error") or login_out.get("response"),
                    },
                    "node_id": node_id,
                    "flow_id": flow_id,
                    "env": env_n,
                    "login_required": True,
                }
        if not access_token and user and password:
            access_token = _identity_login(
                identity_base=identity_base, user=user, password=password
            )

    svc = str(node.get("service") or "")
    tools = list(list_tools(service=svc, limit=1000).get("tools") or []) if svc else []
    pin_qt = None
    if doc.get("payload_set_version") is not None:
        try:
            pin_qt = int(doc.get("payload_set_version"))
        except (TypeError, ValueError):
            pin_qt = None
    result = _invoke_single_node(
        node,
        user=user,
        password=password,
        identity_base=identity_base,
        gateway_host=gateway_host,
        access_token=access_token,
        merged_vars=merged_vars,
        tools=tools,
        env=eff_env,
        doc=doc,
        payload_set_version=pin_qt,
    )
    result.pop("access_token", None)
    result["node_id"] = str(node.get("id") or node_id)
    result["flow_id"] = flow_id
    result["env"] = env_n
    return result


def start_execution(
    flow_id: str,
    *,
    env: str | None = None,
    credential_id: str | None = None,
    variables: dict[str, Any] | None = None,
    payload_set_version: int | None = None,
    suite_run_id: str | None = None,
) -> dict[str, Any]:
    from specs.config import settings as _settings

    env_n = (env or _settings.default_environment or "dev").strip().lower()
    if env_n == "dig":
        env_n = "dev"
    doc = get_flow(flow_id)
    if not doc:
        raise ValueError(f"flow not found: {flow_id}")
    # Merge execute-time vars over persisted; resolve payload version pin
    doc_vars = doc.get("variables") if isinstance(doc.get("variables"), dict) else {}
    merged = {**doc_vars, **(variables or {})}
    pin = payload_set_version
    if pin is None and doc.get("payload_set_version") is not None:
        try:
            pin = int(doc.get("payload_set_version"))
        except (TypeError, ValueError):
            pin = None
    if pin is None:
        # Fall back to Specs active payload set for the flow's primary service.
        try:
            from specs.flows.runtime import primary_payload_service
            from specs.payloads.payload_store import list_payload_sets

            svc = primary_payload_service(doc)
            if svc:
                active = list_payload_sets(svc).get("active_version")
                if active is not None:
                    pin = int(active)
        except Exception:  # noqa: BLE001
            pin = pin
    eid = ex_store.create_execution(
        flow_id,
        env=env_n,
        credential_id=credential_id,
        variables=merged,
        payload_set_version=pin,
        suite_run_id=suite_run_id,
    )
    threading.Thread(target=_run_sync, args=(eid,), daemon=True).start()
    row = ex_store.get_execution(eid) or {}
    return {
        "execution_id": eid,
        "flow_id": flow_id,
        "env": env_n,
        "payload_set_version": pin,
        "suite_run_id": suite_run_id,
        "trace_id": row.get("trace_id"),
        "correlation_id": row.get("correlation_id"),
        "observability_resources": row.get("observability_resources"),
    }
