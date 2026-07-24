"""Unified FastAPI app — SPT + UI evidence + release-gate on one process."""

from __future__ import annotations

from composition.env_bootstrap import load_env
from composition.runtime import apply_colocated_defaults

load_env()
apply_colocated_defaults()

from fastapi.responses import JSONResponse

from composition.identity import AGENT_ID, DISPLAY_NAME, __version__
from gateway.app import app as release_app
from spt.main import app as spt_app
from ui_evidence.main import app as ui_app

# SPT is the base app (portal, MCP /mcp, /api/*, probes)
app = spt_app
app.title = f"{DISPLAY_NAME} Unified Backend"
app.version = __version__


def _merge_routes(target, source, *, skip_paths: set[str]) -> None:
    existing = {getattr(r, "path", None) for r in target.routes}
    for route in source.routes:
        path = getattr(route, "path", None)
        if path in skip_paths or path in existing:
            continue
        target.routes.append(route)
        if path:
            existing.add(path)


_merge_routes(
    app,
    ui_app,
    skip_paths={"/health", "/metrics", "/docs", "/redoc", "/openapi.json"},
)
_merge_routes(
    app,
    release_app,
    skip_paths={"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"},
)


@app.get("/unified/health")
async def unified_health():
    return JSONResponse(
        {
            "status": "ok",
            "agent_id": AGENT_ID,
            "service": "am-qa-agents",
            "components": ["spt", "ui_evidence", "release_gate"],
        }
    )
