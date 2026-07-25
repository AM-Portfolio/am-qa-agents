"""Unified FastAPI app — specs + UI evidence + release-gate on one process."""

from __future__ import annotations

from composition.env_bootstrap import load_env
from composition.runtime import apply_colocated_defaults

load_env()
apply_colocated_defaults()

from fastapi.responses import JSONResponse

from composition.identity import AGENT_ID, DISPLAY_NAME, __version__
from gateway.app import app as release_app
from specs.main import app as specs_app
from ui_evidence.main import app as ui_app

# Specs is the base app (portal, MCP /mcp, /api/*, probes)
app = specs_app
app.title = f"{DISPLAY_NAME} Unified Backend"
app.version = __version__


def _merge_routes(target, source, *, skip_paths: set[str]) -> None:
    """Merge source routes onto target.

    FastAPI 0.12x nests ``include_router`` as ``_IncludedRouter`` with ``path=None``.
    Treating ``None`` as a unique path key skipped every nested router after the first.
    Re-include those routers onto the target app instead of copying the wrapper.
    """
    existing = {
        getattr(r, "path", None)
        for r in target.routes
        if getattr(r, "path", None) is not None
    }
    for route in source.routes:
        path = getattr(route, "path", None)
        if path in skip_paths:
            continue
        if path is not None and path in existing:
            continue

        if type(route).__name__ == "_IncludedRouter":
            ctx = getattr(route, "include_context", None)
            orig = getattr(route, "original_router", None)
            if orig is not None and ctx is not None:
                prefix = getattr(ctx, "prefix", "") or ""
                # Avoid double-mount if prefix routes already present
                sample = next(
                    (getattr(sr, "path", None) for sr in getattr(orig, "routes", [])),
                    None,
                )
                probe = f"{prefix.rstrip('/')}{sample or ''}" if sample else prefix
                if probe and probe in existing:
                    continue
                target.include_router(orig, prefix=prefix)
                for sr in getattr(orig, "routes", []):
                    sp = getattr(sr, "path", None)
                    if sp:
                        existing.add(f"{prefix.rstrip('/')}{sp}")
                continue

        target.routes.append(route)
        if path is not None:
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

# Reuse ui_evidence /metrics handler (gauges already registered when ui_app imported)
if not any(getattr(r, "path", None) == "/metrics" for r in app.routes):
    for route in ui_app.routes:
        if getattr(route, "path", None) == "/metrics":
            app.routes.append(route)
            break


@app.get("/unified/health")
async def unified_health():
    return JSONResponse(
        {
            "status": "ok",
            "agent_id": AGENT_ID,
            "service": "am-qa-agents",
            "components": ["specs", "ui_evidence", "release_gate"],
        }
    )
