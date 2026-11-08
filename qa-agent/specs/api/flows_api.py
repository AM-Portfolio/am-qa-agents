"""HTTP API for credentials + API flows graph + stepped execute."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from specs.flows.authored_store import AuthoredFlowError, delete_authored, upsert_authored
from specs.flows.catalog import get_flow, query_flows
from specs.flows.graph import build_graph
from specs.flows import executions as ex_store
from specs.flows.runner import start_execution
from specs.security.credential_store import (
    CredentialStoreError,
    delete_credential,
    get_credential_public,
    list_credentials,
    seed_from_spt_env,
    upsert_credential,
)

router = APIRouter(tags=["flows"])


class CredentialUpsert(BaseModel):
    id: Optional[str] = None
    name: str
    kind: str = "identity_login"
    env: str = "prod"
    username: str = ""
    password: Optional[str] = None
    token: Optional[str] = None
    base_url: str = ""
    app_id: str = ""


class FlowUpsert(BaseModel):
    id: Optional[str] = None
    title: str = ""
    gate: str = "prod_safe"
    credential_id: Optional[str] = None
    env_default: Optional[str] = None
    group: str = "other"
    category: str = "general"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_by: str = "authored"
    api_pack: Optional[str] = None
    variables: dict[str, Any] = Field(default_factory=dict)
    payload_set_version: Optional[int] = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: Optional[list[dict[str, Any]]] = None


class FlowScheduleUpsert(BaseModel):
    flow_id: str
    cron: str
    env: str = "prod"
    credential_id: Optional[str] = None
    enabled: bool = True


class FlowExecuteIn(BaseModel):
    env: str = "prod"
    credential_id: Optional[str] = None
    variables: Optional[dict[str, Any]] = None
    payload_set_version: Optional[int] = None


class FlowVariablesIn(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    payload_set_version: Optional[int] = None
    clear_payload_pin: bool = False


class FlowPayloadVersionIn(BaseModel):
    version: int
    activate: bool = True
    pin_on_flow: bool = True
    service: Optional[str] = None


class SuitePreviewIn(BaseModel):
    group: Optional[str] = None
    api_pack: Optional[str] = None
    category: Optional[str] = None


class SuiteExecuteIn(BaseModel):
    flow_ids: list[str] = Field(default_factory=list)
    env: str = "prod"
    credential_id: Optional[str] = None
    payload_set_version: Optional[int] = None
    variables: Optional[dict[str, Any]] = None


# --- Credentials ---


@router.get("/api/credentials")
def api_list_credentials(env: Optional[str] = None, kind: Optional[str] = None) -> dict:
    seed_from_spt_env()
    rows = list_credentials(env=env, kind=kind)
    return {"credentials": rows, "count": len(rows)}


@router.get("/api/credentials/apps")
def api_list_credential_apps() -> dict:
    """Catalog of credential kinds/apps for the Add-credential picker."""
    from specs.security.credential_store import list_credential_apps

    rows = list_credential_apps()
    return {"apps": rows, "count": len(rows)}


@router.get("/api/credentials/{cred_id}")
def api_get_credential(cred_id: str) -> dict:
    row = get_credential_public(cred_id)
    if not row:
        raise HTTPException(status_code=404, detail="credential not found")
    return row


@router.post("/api/credentials")
def api_create_credential(body: CredentialUpsert) -> dict:
    try:
        return upsert_credential(**body.model_dump())
    except CredentialStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/credentials/{cred_id}")
def api_update_credential(cred_id: str, body: CredentialUpsert) -> dict:
    try:
        payload = body.model_dump()
        payload["id"] = cred_id
        return upsert_credential(**payload)
    except CredentialStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/credentials/{cred_id}")
def api_delete_credential(cred_id: str) -> dict:
    if not delete_credential(cred_id):
        raise HTTPException(status_code=404, detail="credential not found")
    return {"deleted": cred_id}


@router.post("/api/credentials/probe-all")
def api_probe_all_credentials(env: Optional[str] = None) -> dict:
    """Probe every credential (optional env filter)."""
    from specs.security.credential_probe import probe_all

    return probe_all(env=env)


@router.post("/api/credentials/{cred_id}/probe")
def api_probe_credential(cred_id: str) -> dict:
    """Live connectivity check for one credential / resource."""
    from specs.security.credential_probe import probe_credential

    out = probe_credential(cred_id)
    if out.get("status") == "missing":
        raise HTTPException(status_code=404, detail="credential not found")
    return out


# --- Flows list / executions (static paths before {flow_id}) ---


@router.get("/api/flows")
def api_list_flows(
    group: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    api_pack: Optional[str] = None,
    service: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: int = 0,
    facets: bool = False,
) -> dict:
    return query_flows(
        group=group,
        category=category,
        q=q,
        api_pack=api_pack,
        service=service,
        limit=limit,
        offset=offset,
        facets=facets,
    )


@router.get("/api/flows/executions")
def api_list_executions(
    flow_id: Optional[str] = None,
    env: Optional[str] = None,
    status: Optional[str] = None,
    suite_run_id: Optional[str] = None,
    limit: int = 50,
) -> dict:
    rows = ex_store.list_executions(
        flow_id=flow_id,
        env=env,
        status=status,
        suite_run_id=suite_run_id,
        limit=limit,
    )
    return {"executions": rows, "count": len(rows)}


@router.get("/api/flows/executions/{execution_id}")
def api_get_execution(execution_id: str) -> dict:
    row = ex_store.get_execution(execution_id)
    if not row:
        raise HTTPException(status_code=404, detail="execution not found")
    return row


@router.get("/api/flows/executions/{execution_id}/obs-logs")
async def api_execution_obs_logs(
    execution_id: str,
    limit: int = 100,
) -> dict:
    """Platform logs (Grafana/Loki) for an API flow execution."""
    row = ex_store.get_execution(execution_id)
    if not row:
        raise HTTPException(status_code=404, detail="execution not found")
    from specs.observability.obs_logs import fetch_obs_logs

    out = await fetch_obs_logs(
        trace_id=row.get("trace_id"),
        correlation_id=row.get("correlation_id"),
        limit=limit,
    )
    out["execution_id"] = execution_id
    return out


@router.post("/api/flows/executions/{execution_id}/stop")
def api_stop_execution(execution_id: str) -> dict:
    if not ex_store.request_stop(execution_id):
        raise HTTPException(status_code=404, detail="execution not found")
    return {"stopping": True, "execution_id": execution_id}


@router.post("/api/flows/suite/preview")
def api_suite_preview(body: SuitePreviewIn) -> dict:
    from specs.flows.runtime import suite_preview

    return suite_preview(
        group=body.group, api_pack=body.api_pack, category=body.category
    )


@router.post("/api/flows/suite/execute")
def api_suite_execute(body: SuiteExecuteIn) -> dict:
    from specs.flows.runtime import suite_execute

    try:
        return suite_execute(
            flow_ids=body.flow_ids,
            env=body.env,
            credential_id=body.credential_id,
            payload_set_version=body.payload_set_version,
            variables=body.variables,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class FlowProposeIn(BaseModel):
    service: str
    group: Optional[str] = None
    category: Optional[str] = None
    env: str = "prod"
    max_scenarios: int = 5
    gate: str = "prod_safe"
    use_llm: bool = True


@router.post("/api/flows/propose")
def api_propose_flows(body: FlowProposeIn) -> dict:
    from specs.flows.propose import propose_scenarios

    return propose_scenarios(**body.model_dump())


@router.get("/api/flows/schedules")
def api_list_schedules(flow_id: Optional[str] = None) -> dict:
    from specs.flows.schedule_store import list_schedules

    rows = list_schedules(flow_id=flow_id)
    return {"schedules": rows, "count": len(rows)}


@router.post("/api/flows/schedules")
def api_upsert_schedule(body: FlowScheduleUpsert) -> dict:
    from specs.flows.schedule_store import ScheduleError
    from specs.flows.scheduler import upsert_and_sync

    try:
        return upsert_and_sync(**body.model_dump())
    except ScheduleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/flows/schedules/{schedule_id}/disable")
def api_disable_schedule(schedule_id: str) -> dict:
    from specs.flows.schedule_store import disable_schedule
    from specs.flows.scheduler import sync_schedule_temporal
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    row = disable_schedule(schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="schedule not found")

    def _sync() -> dict:
        return asyncio.run(sync_schedule_temporal(row))

    with ThreadPoolExecutor(max_workers=1) as pool:
        sync = pool.submit(_sync).result(timeout=45)
    return {"ok": True, "schedule": row, "sync": sync}


@router.post("/api/flows")
def api_create_flow(body: FlowUpsert) -> dict:
    try:
        doc = body.model_dump()
        return upsert_authored(doc, flow_id=body.id)
    except AuthoredFlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/flows/{flow_id}")
def api_get_flow(flow_id: str) -> dict:
    doc = get_flow(flow_id)
    if not doc:
        raise HTTPException(status_code=404, detail="flow not found")
    return doc


@router.get("/api/flows/{flow_id}/graph")
def api_flow_graph(flow_id: str) -> dict:
    g = build_graph(flow_id)
    if not g:
        raise HTTPException(status_code=404, detail="flow not found")
    return g


@router.put("/api/flows/{flow_id}")
def api_update_flow(flow_id: str, body: FlowUpsert) -> dict:
    try:
        doc = body.model_dump()
        doc["id"] = flow_id
        return upsert_authored(doc, flow_id=flow_id)
    except AuthoredFlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/flows/{flow_id}")
def api_delete_flow(flow_id: str) -> dict:
    if not delete_authored(flow_id):
        raise HTTPException(status_code=404, detail="authored flow not found")
    return {"deleted": flow_id}


@router.get("/api/flows/{flow_id}/runtime")
def api_flow_runtime(flow_id: str) -> dict:
    from specs.flows.runtime import get_runtime

    row = get_runtime(flow_id)
    if not row:
        raise HTTPException(status_code=404, detail="flow not found")
    return row


@router.put("/api/flows/{flow_id}/variables")
def api_flow_variables(flow_id: str, body: FlowVariablesIn) -> dict:
    from specs.flows.runtime import set_variables

    try:
        return set_variables(
            flow_id,
            body.variables,
            payload_set_version=body.payload_set_version,
            clear_payload_pin=body.clear_payload_pin,
        )
    except AuthoredFlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/flows/{flow_id}/payload-version")
def api_flow_payload_version(flow_id: str, body: FlowPayloadVersionIn) -> dict:
    from specs.flows.runtime import set_payload_version

    try:
        return set_payload_version(
            flow_id=flow_id,
            service=body.service,
            version=body.version,
            activate=body.activate,
            pin_on_flow=body.pin_on_flow,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthoredFlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/flows/{flow_id}/execute")
def api_execute_flow(flow_id: str, body: FlowExecuteIn) -> dict:
    try:
        return start_execution(
            flow_id,
            env=body.env,
            credential_id=body.credential_id,
            variables=body.variables,
            payload_set_version=body.payload_set_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/flows/{flow_id}/nodes/{node_id}/quick-test")
def api_quick_test_node(flow_id: str, node_id: str, body: FlowExecuteIn) -> dict:
    from specs.flows.runner import quick_test_node

    try:
        return quick_test_node(
            flow_id,
            node_id,
            env=body.env,
            credential_id=body.credential_id,
            variables=body.variables,
        )
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc
