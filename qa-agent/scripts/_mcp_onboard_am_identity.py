from composition.env_bootstrap import load_env
load_env()
from specs.mcp.control import spt_onboard_service
import json
out = spt_onboard_service(service="am-identity", environment="dev", allow_llm=True, wait=True, use_temporal=True)
print(json.dumps({
  "mode": out.get("mode"),
  "status": out.get("status"),
  "workflow_id": out.get("workflow_id"),
  "temporal_error": (out.get("temporal_error") or "")[:120],
  "ok": (out.get("result") or {}).get("ok"),
  "failed_step": (out.get("result") or {}).get("failed_step"),
  "warnings": (out.get("result") or {}).get("warnings"),
  "steps": [
    {"step": s.get("step"), "ok": s.get("ok"), "status": s.get("status"), "duration_ms": s.get("duration_ms"), "error": s.get("error")}
    for s in ((out.get("result") or {}).get("steps") or [])
  ],
}, indent=2))
