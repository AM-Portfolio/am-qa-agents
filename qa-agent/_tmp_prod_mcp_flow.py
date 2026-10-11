"""Drive prod UI (Temporal) + API SPT runs via local MCP/HTTP; poll until done."""
from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any

import httpx

BASE = "http://127.0.0.1:8150"


class McpClient:
    def __init__(self, client: httpx.Client) -> None:
        self._c = client
        self._session: str | None = None

    def connect(self) -> None:
        r = self._c.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "prod-mcp-flow", "version": "0.1"},
                },
            },
            headers={"Accept": "application/json, text/event-stream"},
        )
        r.raise_for_status()
        self._session = r.headers.get("mcp-session-id")
        if self._session:
            self._c.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=self._headers(),
            )

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self._session:
            h["mcp-session-id"] = self._session
        return h

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        r = self._c.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000) % 1_000_000,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            },
            headers=self._headers(),
        )
        r.raise_for_status()
        text = r.text
        # SSE: event: message\ndata: {...}
        data_line = next((ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")), text)
        payload = json.loads(data_line)
        if "error" in payload:
            return payload["error"]
        result = payload.get("result") or {}
        content = result.get("content") or []
        if content and isinstance(content[0], dict) and content[0].get("type") == "text":
            raw = content[0].get("text") or "{}"
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"text": raw}
        return result


def main() -> int:
    rid = f"local-prod-ui-{uuid.uuid4().hex[:8]}"
    body = {
        "release_id": rid,
        "release_name": "local-prod-ui-temporal-mcp",
        "env": "prod",
        "suite": "prod_ui_full",
        "target_url": "https://am.asrax.in",
        "login_mode": "credentials",
        "soak_min": 0,
        "skip_ui": False,
        "skip_sheet": True,
        "skip_drive": True,
        "skip_cliq": True,
        "fixtures": False,
        "use_temporal": True,
        "requested_by": "mcp-local",
    }
    with httpx.Client(base_url=BASE, timeout=180.0) as c:
        health = c.get("/health").json()
        print("HEALTH", health.get("status"), "runs", health.get("runs_total"))

        mcp = McpClient(c)
        mcp.connect()
        print("MCP", mcp.call("spt_health"))

        # --- Temporal UI suite against prod ---
        start = c.post("/v2/releases/ops/start", json=body)
        print("OPS_START", start.status_code, start.text[:400])
        start.raise_for_status()
        started = start.json()
        req = started["request_id"]
        tid = started.get("tracking_id")
        wid = started.get("workflow_id")
        print("UI_WF", "request=", req, "tracking=", tid, "workflow=", wid, "mode=", started.get("mode"))

        # --- API SPT profiles (prod target via catalog / env) ---
        profiles = mcp.call("spt_list_profiles", {"audience": "ci", "limit": 50})
        if isinstance(profiles, dict) and "error" not in profiles:
            items = profiles.get("profiles") or profiles.get("items") or profiles.get("configs") or []
            print("API_PROFILES", len(items) if isinstance(items, list) else profiles)
            # Kick a few stable prod-facing profiles if present
            kicked: list[str] = []
            for row in items if isinstance(items, list) else []:
                name = str(row.get("name") or row.get("config_name") or row.get("id") or "")
                cid = str(row.get("id") or row.get("config_id") or "")
                svc = str(row.get("service") or "")
                env = str(row.get("environment") or row.get("env") or "")
                if env and env.lower() not in {"prod", "production", ""}:
                    continue
                # Prefer smoke / health-ish names; cap to avoid flooding
                key = name.lower()
                if not any(x in key for x in ("smoke", "health", "movers", "fno", "ipo", "auth")):
                    continue
                if not cid:
                    continue
                out = mcp.call(
                    "spt_execute_run",
                    {
                        "config_id": cid,
                        "triggered_by": "mcp-local-prod",
                        "wait": False,
                        "vus": 1,
                        "iterations": 1,
                    },
                )
                rid_run = str((out or {}).get("id") or (out or {}).get("run_id") or "")
                print("API_EXEC", svc, name, cid, "->", rid_run or out)
                if rid_run:
                    kicked.append(rid_run)
                if len(kicked) >= 6:
                    break
            print("API_KICKED", len(kicked), kicked)
        else:
            print("API_PROFILES_ERR", profiles)

        # --- Poll UI release progress + MCP runs ---
        deadline = time.time() + 90 * 60  # suite can take a long time
        last_phase = ""
        while time.time() < deadline:
            prog = c.get(f"/v2/releases/{req}").json()
            phase = prog.get("phase")
            status = prog.get("progress_status") or prog.get("status")
            ui_pct = prog.get("ui_pct")
            if phase != last_phase:
                print("PROGRESS", phase, status, "ui_pct=", ui_pct, "decision=", prog.get("ui_decision"))
                last_phase = phase
            runs = mcp.call("spt_list_runs", {"limit": 10})
            total = (runs or {}).get("total") if isinstance(runs, dict) else None
            print("MCP_RUNS_TOTAL", total)
            if status in {"COMPLETED", "FAILED", "completed", "failed"} or phase == "release_ops_complete":
                print("DONE", json.dumps(prog, indent=2)[:2000])
                break
            time.sleep(20)
        else:
            print("TIMEOUT waiting for UI suite")
            return 1

        final_runs = mcp.call("spt_list_runs", {"limit": 15})
        print("FINAL_RUNS", json.dumps(final_runs, indent=2)[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
