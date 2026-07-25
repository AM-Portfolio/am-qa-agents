"""HTTP adapters for specialists + direct lab integrations (Cliq / OpenProject)."""

from __future__ import annotations

import os
from typing import Any

import httpx
import yaml


def _registry_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "registry", "agents.yaml"))


def load_agent_base_url(agent_id: str) -> str:
    path = os.getenv("QA_AGENT_REGISTRY") or _registry_path()
    if not os.path.isfile(path):
        defaults = {
            "ui-test-agent": os.getenv("UI_TEST_AGENT_BASE_URL", "http://127.0.0.1:8130"),
            "tool-agent": os.getenv("TOOL_AGENT_BASE_URL")
            or os.getenv("TOOL_AGENT_URL")
            or "http://127.0.0.1:8141",
            "fin-agent": os.getenv("FIN_AGENT_BASE_URL", "http://127.0.0.1:8100"),
        }
        if agent_id in defaults:
            return defaults[agent_id].rstrip("/")
        raise FileNotFoundError(f"registry not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for card in data.get("agents") or []:
        if card.get("agent_id") == agent_id:
            env_key = card.get("base_url_env") or ""
            return (os.getenv(env_key) or card.get("default_base_url") or "").rstrip("/")
    raise KeyError(f"unknown agent_id={agent_id}")


class UiTestClient:
    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = (base_url or load_agent_base_url("ui-test-agent")).rstrip("/")
        self._client = client

    async def _http(self) -> httpx.AsyncClient:
        if self._client:
            return self._client
        return httpx.AsyncClient(timeout=60.0)

    async def run_smoke(
        self,
        *,
        target_url: str,
        profile: str,
        commit_sha: str,
        branch: str,
        callback_url: str | None = None,
        tool_agent_base_url: str | None = None,
        gnx_mcp_url: str | None = None,
    ) -> dict[str, Any]:
        from adapters.mcp_fallback import (
            MODE_FALLBACK_GNX,
            MODE_FALLBACK_MCP,
            MODE_FALLBACK_TEMPLATE,
            MODE_LIVE,
            MODE_SKIPPED,
            _mcp_text,
            a2a_execute,
            gnx_mcp_call,
        )

        if os.getenv("QA_AGENT_SKIP_UI_TEST", "").lower() in {"1", "true", "yes"}:
            return await self._ui_mcp_fallbacks(
                target_url=target_url,
                profile=profile,
                commit_sha=commit_sha,
                branch=branch,
                tool_agent_base_url=tool_agent_base_url,
                gnx_mcp_url=gnx_mcp_url,
                prior="QA_AGENT_SKIP_UI_TEST",
            )

        body: dict[str, Any] = {
            "targetUrl": target_url,
            "profile": profile,
            "commitSha": commit_sha,
            "branch": branch,
            "baselineMode": "compare",
            "uiMode": "main",
            "specification": "qa-agent release readiness",
        }
        if callback_url:
            body["callbackUrl"] = callback_url
        owns = self._client is None
        client = await self._http()
        try:
            resp = await client.post(f"{self.base_url}/api/v1/test/run", json=body)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"body": resp.text}
            if resp.status_code >= 400:
                return await self._ui_mcp_fallbacks(
                    target_url=target_url,
                    profile=profile,
                    commit_sha=commit_sha,
                    branch=branch,
                    tool_agent_base_url=tool_agent_base_url,
                    gnx_mcp_url=gnx_mcp_url,
                    prior=f"ui_http_{resp.status_code}",
                )
            test_id = ""
            if isinstance(data, dict):
                test_id = str(data.get("testId") or data.get("test_id") or "")
            if test_id:
                status = await self.poll_status(test_id, client=client)
                return {"testId": test_id, "mode": MODE_LIVE, **status, "start": data}
            return {**(data if isinstance(data, dict) else {"data": data}), "mode": MODE_LIVE}
        except httpx.HTTPError as exc:
            return await self._ui_mcp_fallbacks(
                target_url=target_url,
                profile=profile,
                commit_sha=commit_sha,
                branch=branch,
                tool_agent_base_url=tool_agent_base_url,
                gnx_mcp_url=gnx_mcp_url,
                prior=str(exc),
            )
        finally:
            if owns:
                await client.aclose()

    async def _ui_mcp_fallbacks(
        self,
        *,
        target_url: str,
        profile: str,
        commit_sha: str,
        branch: str,
        tool_agent_base_url: str | None,
        gnx_mcp_url: str | None,
        prior: str,
    ) -> dict[str, Any]:
        from adapters.mcp_fallback import (
            MODE_FALLBACK_GNX,
            MODE_FALLBACK_MCP,
            MODE_FALLBACK_TEMPLATE,
            MODE_SKIPPED,
            _mcp_text,
            a2a_execute,
            gnx_mcp_call,
        )

        a2a = await a2a_execute(
            capability="observe.metrics.query",
            payload={
                "services": ["ui", profile],
                "target_url": target_url,
                "profile": profile,
                "commit_sha": commit_sha,
                "branch": branch,
            },
            base_url=tool_agent_base_url,
        )
        if a2a.get("ok") and isinstance(a2a.get("data"), dict):
            return {
                "skipped": True,
                "status": "SKIPPED",
                "mode": MODE_FALLBACK_MCP,
                "via": a2a.get("via") or "tool_agent_execute",
                "capability": a2a.get("capability"),
                "profile": profile,
                "data": a2a["data"],
                "prior": prior,
                "note": "Advisory MCP only — replace with ui-test-agent when Vault secrets exist",
            }

        gnx_args: dict[str, Any] = {
            "search_query": f"ui auth login smoke {profile} {target_url}",
            "limit": 4,
        }
        ui_repo = (os.getenv("QA_AGENT_UI_REPO") or "").strip()
        if ui_repo:
            gnx_args["repo"] = ui_repo
        gnx = await gnx_mcp_call(
            tool="query",
            arguments=gnx_args,
            base_url=gnx_mcp_url,
        )
        if gnx.get("ok"):
            return {
                "skipped": True,
                "status": "SKIPPED",
                "mode": MODE_FALLBACK_GNX,
                "via": "gnx_mcp",
                "profile": profile,
                "gnx_preview": _mcp_text(gnx)[:1200],
                "prior": prior,
                "note": "Replace fallback_gnx with ui-test-agent when Vault secrets exist",
            }

        return {
            "skipped": True,
            "status": "SKIPPED",
            "mode": MODE_FALLBACK_TEMPLATE if "SKIP_UI" not in prior else MODE_SKIPPED,
            "profile": profile,
            "prior": prior,
            "a2a_ok": a2a.get("ok"),
            "note": "Honest skip — not a fake COMPLETED; replace with ui-test-agent",
        }

    async def poll_status(
        self,
        test_id: str,
        *,
        client: httpx.AsyncClient | None = None,
        max_polls: int = 30,
        interval_s: float = 2.0,
    ) -> dict[str, Any]:
        import asyncio

        owns = client is None
        http = client or await self._http()
        try:
            last: dict[str, Any] = {}
            for _ in range(max_polls):
                resp = await http.get(f"{self.base_url}/api/v1/test/status/{test_id}")
                data = resp.json() if resp.status_code < 400 else {"http_status": resp.status_code}
                last = data if isinstance(data, dict) else {"body": data}
                st = str(last.get("status") or "").lower()
                if st in {"done", "completed", "succeeded", "success", "passed", "failed", "error"}:
                    return last
                await asyncio.sleep(interval_s)
            return {**last, "status": "TIMEOUT"}
        finally:
            if owns:
                await http.aclose()


class NotifyClient:
    """Cliq webhook (lab) with tool-agent chat fallback."""

    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = (
            base_url
            or os.getenv("TOOL_AGENT_BASE_URL")
            or os.getenv("TOOL_AGENT_URL")
            or load_agent_base_url("tool-agent")
        ).rstrip("/")
        self._client = client

    async def send_cliq_card(self, *, title: str, body: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        if os.getenv("QA_AGENT_SKIP_NOTIFY", "").lower() in {"1", "true", "yes"}:
            return {"skipped": True, "title": title, "body": body, "meta": meta or {}}

        webhook = (
            os.getenv("QA_AGENT_CLIQ_WEBHOOK_URL")
            or os.getenv("ZOHO_CLIQ_WEBHOOK_URL")
            or os.getenv("ZOHO_CLIQ_LAB_WEBHOOK_URL")
            or ""
        ).strip()
        owns = self._client is None
        http = self._client or httpx.AsyncClient(timeout=30.0)
        try:
            if webhook:
                text = f"*{title}*\n```\n{body}\n```"
                resp = await http.post(webhook, json={"text": text})
                if resp.status_code < 400:
                    return {
                        "ok": True,
                        "via": "cliq_webhook",
                        "http_status": resp.status_code,
                        "title": title,
                    }

            from adapters.mcp_fallback import a2a_execute

            a2a = await a2a_execute(
                capability="chat.message.send",
                payload={
                    "channel": os.getenv("QA_AGENT_CLIQ_CHANNEL", "qa-agent"),
                    "title": title,
                    "text": body,
                    "meta": meta or {},
                },
                base_url=self.base_url,
                read_only=False,
            )
            if not a2a.get("ok"):
                return {
                    "status": "stubbed",
                    "http_status": a2a.get("http_status"),
                    "title": title,
                    "body": body,
                    "via": "tool_agent",
                    "error": a2a.get("error"),
                    "mode": "fallback_template",
                }
            data = a2a.get("data") if isinstance(a2a.get("data"), dict) else {"ok": True}
            return {**data, "via": "tool_agent", "mode": "fallback_mcp"}
        except httpx.HTTPError as exc:
            return {"status": "stubbed", "error": str(exc), "title": title, "body": body}
        finally:
            if owns:
                await http.aclose()


class WorkItemClient:
    """OpenProject direct API, else tool-agent work-item.create."""

    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = (
            base_url
            or os.getenv("TOOL_AGENT_BASE_URL")
            or os.getenv("TOOL_AGENT_URL")
            or load_agent_base_url("tool-agent")
        ).rstrip("/")
        self._client = client

    async def create(
        self,
        *,
        subject: str,
        description: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if os.getenv("QA_AGENT_SKIP_WORK_ITEM", "").lower() in {"1", "true", "yes"}:
            return {
                "skipped": True,
                "kind": "dev_handoff_ticket",
                "mode": "ticket_only",
                "subject": subject,
                "description": description,
                "meta": meta or {},
                "work_item_id": f"local-{(meta or {}).get('tracking_id') or 'stub'}",
            }

        op_url = (os.getenv("OPENPROJECT_URL") or "").rstrip("/")
        op_token = os.getenv("OPENPROJECT_API_TOKEN") or ""
        project_id = os.getenv("QA_AGENT_OP_PROJECT_ID") or os.getenv("OPENPROJECT_PROJECT_ID") or "3"
        type_id = os.getenv("OPENPROJECT_TYPE_ID") or "1"

        owns = self._client is None
        http = self._client or httpx.AsyncClient(timeout=30.0)
        try:
            if op_url and op_token:
                # OpenProject APIv3 work package create
                body = {
                    "subject": subject[:255],
                    "description": {"format": "plain", "raw": description},
                    "_links": {
                        "type": {"href": f"/api/v3/types/{type_id}"},
                        "project": {"href": f"/api/v3/projects/{project_id}"},
                    },
                }
                assignee = os.getenv("OPENPROJECT_DEFAULT_ASSIGNEE_ID")
                if assignee:
                    body["_links"]["assignee"] = {"href": f"/api/v3/users/{assignee}"}
                resp = await http.post(
                    f"{op_url}/api/v3/work_packages",
                    headers={
                        "Authorization": f"Basic {__import__('base64').b64encode(('apikey:' + op_token).encode()).decode()}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                data = (
                    resp.json()
                    if resp.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                if resp.status_code < 400 and isinstance(data, dict):
                    wid = str(data.get("id") or data.get("_links", {}).get("self", {}).get("href") or "")
                    return {
                        "kind": "dev_handoff_ticket",
                        "mode": "ticket_only",
                        "via": "openproject",
                        "work_item_id": wid or f"op-{(meta or {}).get('tracking_id')}",
                        "url": f"{op_url}/work_packages/{data.get('id')}" if data.get("id") else None,
                        "subject": subject,
                        "http_status": resp.status_code,
                    }
                # fall through to tool-agent on OP failure

            from adapters.mcp_fallback import a2a_execute

            a2a = await a2a_execute(
                capability="work-item.create",
                payload={
                    "subject": subject,
                    "description": description,
                    "project": os.getenv("QA_AGENT_OP_PROJECT", project_id),
                    "meta": meta or {},
                },
                base_url=self.base_url,
                read_only=False,
            )
            if not a2a.get("ok"):
                return {
                    "kind": "dev_handoff_ticket",
                    "mode": "ticket_only",
                    "status": "stubbed",
                    "http_status": a2a.get("http_status"),
                    "subject": subject,
                    "description": description,
                    "work_item_id": f"stub-{(meta or {}).get('tracking_id') or 'x'}",
                    "error": a2a.get("error"),
                }
            data = a2a.get("data") if isinstance(a2a.get("data"), dict) else {"ok": True}
            if isinstance(data, dict):
                return {
                    "kind": "dev_handoff_ticket",
                    "mode": "ticket_only",
                    "via": "tool_agent",
                    **data,
                    "subject": subject,
                }
            return {
                "kind": "dev_handoff_ticket",
                "mode": "ticket_only",
                "via": "tool_agent",
                "data": data,
                "subject": subject,
            }
        except httpx.HTTPError as exc:
            return {
                "kind": "dev_handoff_ticket",
                "mode": "ticket_only",
                "status": "stubbed",
                "error": str(exc),
                "subject": subject,
                "description": description,
                "work_item_id": f"stub-{(meta or {}).get('tracking_id') or 'x'}",
            }
        finally:
            if owns:
                await http.aclose()
