"""One-shot dogfood: seed creds + execute pack:subscription via MCP tools."""
from __future__ import annotations

import os
import time
from pathlib import Path


def _load_dotenv() -> None:
    for p in (Path(__file__).resolve().parents[1] / ".env", Path.cwd() / ".env"):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    _load_dotenv()
    from specs.security.credential_store import seed_from_spt_env
    from specs.mcp.control import (
        qa_credential_list,
        qa_flow_execute,
        qa_flow_execution_get,
        qa_flow_graph,
        qa_flow_list,
    )

    seeded = seed_from_spt_env()
    print("seed", seeded)
    creds = qa_credential_list()
    print("creds_count", creds.get("count"))
    flows = qa_flow_list()
    print("flow_count", flows.get("count"))
    g = qa_flow_graph("pack:subscription")
    print(
        "graph_ok",
        g.get("ok"),
        "nodes",
        len((g.get("graph") or {}).get("nodes") or []),
    )
    cred_id = None
    rows = creds.get("credentials") or []
    if rows:
        cred_id = rows[0].get("id")
    ex = qa_flow_execute("pack:subscription", env="prod", credential_id=cred_id)
    print("execute", ex)
    if not ex.get("ok"):
        return 1
    eid = ex["execution_id"]
    for i in range(45):
        time.sleep(0.8)
        st = qa_flow_execution_get(eid)
        execu = st.get("execution") or {}
        status = execu.get("status")
        print("poll", i, status, execu.get("summary") or execu.get("error"))
        if status in ("finished", "failed", "error", "stopped"):
            summary = execu.get("summary") or {}
            return 0 if summary.get("ok") or status == "finished" else 2
    print("timeout")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
