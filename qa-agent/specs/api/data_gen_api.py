"""REST API for am-specs data-gen import / suite / pipeline."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

router = APIRouter(tags=["data-gen"])


class DataGenImportBody(BaseModel):
    service: str
    profile: str = "default"
    environment: str = "dev"
    payload_set: dict[str, Any] | None = None
    collection: dict[str, Any] | None = None
    pack_path: str | None = None
    make_active: bool = True
    sync_workflows: bool = True
    env: dict[str, Any] | None = None
    # Prefer zip_b64 for large packs (deflated JSON) — expands before import.
    zip_b64: str | None = None
    gzip_b64: str | None = None
    zip_filename: str | None = None


class DataGenSuiteBody(BaseModel):
    service: str
    profile: str = "default"
    environment: str = "dev"
    case_kinds: list[str] | None = None
    payload_set_version: int | None = None
    wait: bool = False


class DataGenWorkflowsBody(BaseModel):
    service: str
    profile: str = "default"
    environment: str = "dev"
    flow_id: str | None = None
    payload_set_version: int | None = None
    strict_workflows: bool = False


class DataGenPipelineBody(BaseModel):
    service: Optional[str] = None
    services: list[str] | None = None
    profile: Optional[str] = None
    environment: Optional[str] = None
    git_ref: Optional[str] = None
    payload_set: dict[str, Any] | None = None
    pack_path: Optional[str] = None
    fill_gaps: bool = True
    run_suite: bool = True
    run_workflows: bool = True
    strict_workflows: bool = False
    strict_payloads: bool = False
    allow_llm: Optional[bool] = None
    resume_from: Optional[str] = None
    prior_receipt: dict[str, Any] | None = None
    wait_suite: bool = False


class DataGenImportBatchBody(BaseModel):
    """Batch feed: list of per-service×profile import items (zip_b64 preferred)."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    environment: str = "dev"


@router.post("/api/data-gen/import-batch")
async def api_data_gen_import_batch(body: DataGenImportBatchBody) -> dict:
    """Sequential multi pack import; continues on failure. Prefer zip_b64 per item."""
    from specs.data_gen.batch_import import import_batch

    return import_batch(body.items, default_environment=body.environment)


@router.post("/api/data-gen/import")
async def api_data_gen_import(body: DataGenImportBody) -> dict:
    from specs.data_gen.import_svc import import_data_gen
    from specs.payloads.zip_codec import ZipCodecError, maybe_expand_import_fields

    try:
        expanded = maybe_expand_import_fields(body.model_dump())
    except ZipCodecError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = str(expanded.get("service") or body.service)
    profile = str(expanded.get("profile") or body.profile)
    environment = str(expanded.get("environment") or body.environment)
    payload_set = expanded.get("payload_set")
    collection = expanded.get("collection")
    env = expanded.get("env") if expanded.get("env") is not None else body.env

    merged = None
    if payload_set or collection or env:
        merged = {
            "payload_set": payload_set,
            "collection": collection,
            "env": env,
            "label": None,
        }
    out = import_data_gen(
        service=service,
        profile=profile,
        environment=environment,
        body=merged,
        pack_path=body.pack_path,
        make_active=body.make_active,
        sync_workflows=body.sync_workflows,
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out)
    return out


@router.post("/api/data-gen/import-zip")
async def api_data_gen_import_zip(
    file: UploadFile = File(...),
    service: str = Form(...),
    profile: str = Form("default"),
    environment: str = Form("dev"),
    make_active: bool = Form(True),
    sync_workflows: bool = Form(True),
) -> dict:
    """Multipart zip/gzip/json upload for large data-gen packs."""
    from specs.data_gen.import_svc import import_data_gen
    from specs.payloads.zip_codec import ZipCodecError, unpack_blob

    raw = await file.read()
    try:
        doc = unpack_blob(raw, filename=file.filename)
    except ZipCodecError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not isinstance(doc, dict):
        raise HTTPException(status_code=400, detail="zip JSON root must be an object")

    payload_set = doc.get("payload_set") if isinstance(doc.get("payload_set"), dict) else None
    collection = doc.get("collection") if isinstance(doc.get("collection"), dict) else None
    env = doc.get("env") if isinstance(doc.get("env"), dict) else None
    if payload_set is None and "apis" in doc:
        payload_set = doc
    if payload_set is None and collection is None:
        collection = doc

    merged = {
        "payload_set": payload_set,
        "collection": collection,
        "env": env,
        "label": None,
    }
    svc = (service or str(doc.get("service") or "")).strip()
    if not svc:
        raise HTTPException(status_code=400, detail="service required")
    out = import_data_gen(
        service=svc,
        profile=str(doc.get("profile") or profile),
        environment=str(doc.get("environment") or environment),
        body=merged,
        pack_path=None,
        make_active=make_active,
        sync_workflows=sync_workflows,
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out)
    out["transfer"] = {
        "filename": file.filename,
        "bytes_in": len(raw),
        "encoding": (
            "zip"
            if raw[:2] == b"PK"
            else ("gzip" if raw[:2] == b"\x1f\x8b" else "json")
        ),
    }
    return out


@router.post("/api/data-gen/gapfill")
async def api_data_gen_gapfill(
    service: str,
    environment: str = "dev",
    payload_set_version: int | None = None,
    allow_llm: bool = True,
) -> dict:
    from specs.data_gen.pipeline import data_gen_gapfill

    return data_gen_gapfill(
        service=service,
        environment=environment,
        payload_set_version=payload_set_version,
        allow_llm=allow_llm,
    )


@router.post("/api/data-gen/run-suite")
async def api_data_gen_run_suite(body: DataGenSuiteBody) -> dict:
    from specs.data_gen.pipeline import data_gen_run_suite

    out = data_gen_run_suite(
        service=body.service,
        profile=body.profile,
        environment=body.environment,
        case_kinds=body.case_kinds,
        payload_set_version=body.payload_set_version,
        wait=body.wait,
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out)
    return out


@router.post("/api/data-gen/run-workflows")
async def api_data_gen_run_workflows(body: DataGenWorkflowsBody) -> dict:
    from specs.data_gen.pipeline import data_gen_run_workflows

    return data_gen_run_workflows(
        service=body.service,
        profile=body.profile,
        environment=body.environment,
        flow_id=body.flow_id,
        payload_set_version=body.payload_set_version,
        strict_workflows=body.strict_workflows,
    )


@router.get("/api/data-gen/workflows")
async def api_data_gen_list_workflows(
    service: str | None = None,
    profile: str | None = None,
    flow_id: str | None = None,
) -> dict:
    from specs.data_gen.workflows import list_data_gen_workflows

    rows = list_data_gen_workflows(service=service, profile=profile, flow_id=flow_id)
    return {"ok": True, "flows": rows, "count": len(rows)}


@router.post("/api/data-gen/pipeline")
async def api_data_gen_pipeline(body: DataGenPipelineBody) -> dict:
    from specs.data_gen.pipeline import data_gen_pipeline

    merged = None
    if body.payload_set:
        merged = {"payload_set": body.payload_set}
    return data_gen_pipeline(
        service=body.service,
        services=body.services,
        profile=body.profile,
        environment=body.environment,
        git_ref=body.git_ref,
        body=merged,
        pack_path=body.pack_path,
        fill_gaps=body.fill_gaps,
        run_suite=body.run_suite,
        run_workflows=body.run_workflows,
        strict_workflows=body.strict_workflows,
        strict_payloads=body.strict_payloads,
        allow_llm=body.allow_llm,
        resume_from=body.resume_from,
        prior_receipt=body.prior_receipt,
        wait_suite=body.wait_suite,
    )


@router.get("/api/data-gen/resolve-branch")
async def api_data_gen_resolve_branch(
    git_ref: str | None = None,
    profile: str | None = None,
    environment: str | None = None,
) -> dict:
    from specs.data_gen.branch import resolve_branch_defaults

    return {"ok": True, **resolve_branch_defaults(git_ref=git_ref, profile=profile, environment=environment)}
