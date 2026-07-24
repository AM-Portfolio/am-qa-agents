#!/usr/bin/env python3
"""Create/update Postman collection + environment for qa-agent local pilot.

Uses POSTMAN_API_KEY from env (same key as Cursor Postman MCP).
Does not print the key.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.getpostman.com"
COLLECTION_NAME = "qa-agent-local"
ENV_NAME = "qa-agent-local"


def _req(method: str, path: str, key: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "X-Api-Key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Postman API {method} {path} -> {exc.code}: {err[:800]}") from exc


def _collection_def(token: str) -> dict:
    auth_header = {
        "key": "Authorization",
        "value": "Bearer {{token}}",
        "type": "text",
    }
    allow_body = {
        "repo": "ssd2658/am-core-services",
        "branch": "master",
        "head_sha": "deadbeefcafebabe01",
        "service": "am-analysis",
        "ci_conclusion": "success",
        "trigger_kind": "ci_master_merge",
        "environment": "dev",
        "assume_ci_success": True,
        "use_temporal": True,
    }
    deny_body = {**allow_body, "service": "am-gateway", "head_sha": "deadbeefcafebabe02"}
    return {
        "info": {
            "name": COLLECTION_NAME,
            "description": "qa-agent local pilot (am-analysis). Updated via Cursor Postman MCP / sync script.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "baseUrl", "value": "http://127.0.0.1:8150"},
            {"key": "token", "value": token},
            {"key": "tracking_id", "value": ""},
        ],
        "item": [
            {
                "name": "health",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": "{{baseUrl}}/health",
                },
            },
            {
                "name": "release-readiness allow am-analysis",
                "request": {
                    "method": "POST",
                    "header": [
                        auth_header,
                        {"key": "Content-Type", "value": "application/json"},
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps(allow_body, indent=2),
                        "options": {"raw": {"language": "json"}},
                    },
                    "url": "{{baseUrl}}/v2/workflows/release-readiness",
                },
            },
            {
                "name": "release-readiness deny am-gateway",
                "request": {
                    "method": "POST",
                    "header": [
                        auth_header,
                        {"key": "Content-Type", "value": "application/json"},
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps(deny_body, indent=2),
                        "options": {"raw": {"language": "json"}},
                    },
                    "url": "{{baseUrl}}/v2/workflows/release-readiness",
                },
            },
            {
                "name": "HITL approve.release",
                "request": {
                    "method": "POST",
                    "header": [
                        auth_header,
                        {"key": "Content-Type", "value": "application/json"},
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps(
                            {"actor": "operator", "notes": "local approve"}, indent=2
                        ),
                        "options": {"raw": {"language": "json"}},
                    },
                    "url": "{{baseUrl}}/v2/runs/{{tracking_id}}/signals/approve.release",
                },
            },
            {
                "name": "HITL reject.release",
                "request": {
                    "method": "POST",
                    "header": [
                        auth_header,
                        {"key": "Content-Type", "value": "application/json"},
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps(
                            {"actor": "operator", "notes": "local reject"}, indent=2
                        ),
                        "options": {"raw": {"language": "json"}},
                    },
                    "url": "{{baseUrl}}/v2/runs/{{tracking_id}}/signals/reject.release",
                },
            },
        ],
    }


def _env_def(token: str) -> dict:
    return {
        "name": ENV_NAME,
        "values": [
            {"key": "baseUrl", "value": "http://127.0.0.1:8150", "enabled": True},
            {"key": "token", "value": token, "enabled": True},
            {"key": "tracking_id", "value": "", "enabled": True},
        ],
    }


def main() -> int:
    key = (os.getenv("POSTMAN_API_KEY") or "").strip()
    if not key:
        print("Set POSTMAN_API_KEY", file=sys.stderr)
        return 2
    token = os.getenv("QA_AGENT_GATEWAY_TOKEN", "dev-token-change-me")

    me = _req("GET", "/me", key)
    user = (me.get("user") or {}).get("username") or (me.get("user") or {}).get("id")
    print(f"Postman user ok: {user}")

    workspaces = (_req("GET", "/workspaces", key).get("workspaces") or [])
    ws_id = None
    for w in workspaces:
        if w.get("name") in {"My Workspace", "Team Workspace"} or w.get("type") == "personal":
            ws_id = w.get("id")
            if w.get("type") == "personal":
                break
    if not ws_id and workspaces:
        ws_id = workspaces[0].get("id")
    if not ws_id:
        raise SystemExit("No Postman workspace found")
    print(f"workspace={ws_id}")

    collections = (_req("GET", "/collections", key).get("collections") or [])
    existing_uid = next((c.get("uid") for c in collections if c.get("name") == COLLECTION_NAME), None)
    coll_body = {"collection": _collection_def(token)}
    if existing_uid:
        out = _req("PUT", f"/collections/{existing_uid}", key, coll_body)
        print(f"updated collection uid={existing_uid}")
    else:
        out = _req("POST", f"/collections?workspace={ws_id}", key, coll_body)
        existing_uid = (out.get("collection") or {}).get("uid")
        print(f"created collection uid={existing_uid}")

    envs = (_req("GET", "/environments", key).get("environments") or [])
    env_uid = next((e.get("uid") for e in envs if e.get("name") == ENV_NAME), None)
    env_body = {"environment": _env_def(token)}
    if env_uid:
        _req("PUT", f"/environments/{env_uid}", key, env_body)
        print(f"updated environment uid={env_uid}")
    else:
        out_e = _req("POST", f"/environments?workspace={ws_id}", key, env_body)
        env_uid = (out_e.get("environment") or {}).get("uid")
        print(f"created environment uid={env_uid}")

    print("Done. In Postman: open collection qa-agent-local, select env qa-agent-local, Send.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
