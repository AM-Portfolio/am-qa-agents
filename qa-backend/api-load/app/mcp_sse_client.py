"""SSE MCP client for Spring AI am-mcp-server (/sse + /message).

SPT's RemoteMcpClient uses streamable HTTP; am-mcp-server does not.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class McpSseClient:
    """One-shot SSE session: initialize, tools/call, close."""

    def __init__(
        self,
        base_url: str,
        *,
        bearer_token: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base = base_url.rstrip("/")
        # Public ingress is …/mcp; cluster is host:8080 with no /mcp.
        self.bearer_token = bearer_token
        self.timeout_seconds = timeout_seconds
        self.session_id: str | None = None
        self.message_path = "/message"
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._stop = False
        self._thread: threading.Thread | None = None
        self._rpc_id = 0

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        # Some ingress / WAF rules reject the default Python-urllib User-Agent (403).
        h: dict[str, str] = {"User-Agent": "am-spt-poc/0.1"}
        if self.bearer_token:
            h["Authorization"] = f"Bearer {self.bearer_token}"
        if extra:
            h.update(extra)
        return h

    def __enter__(self) -> McpSseClient:
        self._thread = threading.Thread(target=self._read_sse, daemon=True)
        self._thread.start()
        if not self._ready.wait(min(20.0, self.timeout_seconds)):
            self.close()
            raise TimeoutError(f"SSE session not ready at {self.base}/sse")
        self._post_rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "am-spt-poc", "version": "0.1"},
            },
        )
        self._post_raw({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._stop = True

    def _read_sse(self) -> None:
        req = Request(
            f"{self.base}/sse",
            headers=self._headers({"Accept": "text/event-stream"}),
        )
        try:
            # timeout=None: SSE stays open until tool responses arrive (idle gaps are normal).
            with urlopen(req, timeout=None) as resp:
                event: str | None = None
                data_lines: list[str] = []
                while not self._stop:
                    line = resp.readline().decode("utf-8", errors="replace")
                    if not line:
                        break
                    line = line.rstrip("\n")
                    if line.startswith("id:"):
                        self.session_id = line[3:].strip()
                    elif line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
                    elif line == "":
                        if not data_lines:
                            continue
                        data = "\n".join(data_lines)
                        data_lines = []
                        if event == "endpoint":
                            path = data.strip() or "/message"
                            # endpoint may be absolute path or full URL path
                            if path.startswith("http"):
                                from urllib.parse import urlparse

                                parsed = urlparse(path)
                                self.message_path = parsed.path or "/message"
                                if parsed.query:
                                    # keep query for session; sessionId still appended
                                    self.message_path = f"{self.message_path}?{parsed.query}"
                            else:
                                self.message_path = path
                            if self.session_id or "sessionId=" in self.message_path:
                                self._ready.set()
                        elif event == "message":
                            try:
                                payload = json.loads(data)
                            except json.JSONDecodeError:
                                payload = {"raw": data}
                            with self._lock:
                                self._events.append(payload)
                        event = None
        except (HTTPError, URLError, OSError) as exc:
            logger.warning("MCP SSE read failed: %s", exc)
            self._ready.set()  # unblock waiter; subsequent calls will fail clearly

    def _post_raw(self, body: dict[str, Any]) -> None:
        if not self.session_id and "sessionId=" not in self.message_path:
            raise RuntimeError("MCP SSE sessionId missing")
        path = self.message_path
        if "sessionId=" not in path:
            sep = "&" if "?" in path else "?"
            path = f"{path}{sep}sessionId={self.session_id}"
        if path.startswith("http"):
            url = path
        else:
            url = f"{self.base}{path}"
        req = Request(
            url,
            data=json.dumps(body).encode(),
            headers=self._headers({"Content-Type": "application/json"}),
            method="POST",
        )
        with urlopen(req, timeout=self.timeout_seconds) as resp:
            resp.read()

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _post_rpc(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        rpc_id = self._next_id()
        self._post_raw(
            {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params or {}}
        )
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            with self._lock:
                for i, ev in enumerate(self._events):
                    if ev.get("id") == rpc_id:
                        return self._events.pop(i)
            time.sleep(0.05)
        raise TimeoutError(f"No SSE response for {method} id={rpc_id}")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        resp = self._post_rpc(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        if "error" in resp:
            raise RuntimeError(f"MCP tool {name}: {resp['error']}")
        result = resp.get("result", resp)
        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, list) and content:
            texts = [c.get("text", "") for c in content if isinstance(c, dict)]
            joined = "\n".join(t for t in texts if t)
            try:
                return json.loads(joined)
            except json.JSONDecodeError:
                return joined
        return result


def call_mcp_tool(
    base_url: str,
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    bearer_token: str | None = None,
    timeout_seconds: float = 30.0,
) -> Any:
    """Fresh SSE session per tool call (avoids long-lived stream recycle issues)."""
    with McpSseClient(
        base_url,
        bearer_token=bearer_token,
        timeout_seconds=timeout_seconds,
    ) as client:
        return client.call_tool(tool, arguments)
