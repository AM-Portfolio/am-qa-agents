"""Cliq chat gate: one admin must approve before AsraxReleaseOpsWorkflow starts."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def release_admin() -> str:
    """Single approver identity (email or Cliq user id)."""
    return (
        os.getenv("QA_AGENT_RELEASE_ADMIN")
        or os.getenv("ASRAX_RELEASE_ADMIN")
        or ""
    ).strip().lower()


def gateway_public_base() -> str:
    return (
        os.getenv("QA_AGENT_PUBLIC_BASE_URL")
        or os.getenv("QA_AGENT_BASE_URL")
        or f"http://127.0.0.1:{os.getenv('QA_AGENT_PORT', '8150')}"
    ).rstrip("/")


def _token_secret() -> bytes:
    raw = (
        os.getenv("QA_AGENT_CLIQ_RELEASE_SECRET")
        or os.getenv("QA_AGENT_GATEWAY_TOKEN")
        or "local-dev-release-secret"
    ).strip()
    return raw.encode("utf-8")


def sign_request(request_id: str, action: str) -> str:
    msg = f"{request_id}:{action}".encode("utf-8")
    return hmac.new(_token_secret(), msg, hashlib.sha256).hexdigest()


def verify_token(request_id: str, action: str, token: str) -> bool:
    expected = sign_request(request_id, action)
    return hmac.compare_digest(expected, (token or "").strip())


def is_release_admin(actor: str) -> bool:
    admin = release_admin()
    if not admin:
        # Local/dev: allow if admin unset and env is local
        env = (os.getenv("QA_AGENT_ENV") or "local").lower()
        return env in {"local", "dev", "test"}
    actor_n = (actor or "").strip().lower()
    if not actor_n:
        return False
    if actor_n == admin:
        return True
    # allow email local-part match when admin is full email
    if "@" in admin and actor_n == admin.split("@", 1)[0]:
        return True
    return False


@dataclass
class PendingReleaseRequest:
    request_id: str
    status: str = "pending"  # pending | approved | rejected | started | failed
    created_at: str = field(default_factory=_utc)
    updated_at: str = field(default_factory=_utc)
    requested_by: str = ""
    release_id: str = ""
    release_name: str = ""
    env: str = "prod"
    suite: str = "prod_ui_full"
    api_pack: str = ""  # e.g. "subscription" — run scoped API pack with UI suite
    target_url: str = "https://am.asrax.in"
    login_mode: str = "credentials"
    soak_min: int = 30
    skip_ui: bool = False
    skip_sheet: bool = False
    skip_drive: bool = False
    skip_cliq: bool = False
    fixtures: bool = False
    use_temporal: bool = True
    admin: str = ""
    decision_actor: str = ""
    decision_notes: str = ""
    workflow_id: str = ""
    tracking_id: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def workflow_args(self) -> dict[str, Any]:
        api_pack = self.api_pack or ""
        if not api_pack:
            try:
                from ui_evidence.plugins.loader import resolve_api_pack_default

                api_pack = resolve_api_pack_default(self.suite)
            except Exception:  # noqa: BLE001
                api_pack = (
                    "subscription" if self.suite == "subscription_module" else ""
                )
        return {
            "tracking_id": self.tracking_id or f"qa-{uuid.uuid4().hex[:12]}",
            "release_id": self.release_id or None,
            "release_name": self.release_name or self.release_id,
            "env": self.env,
            "suite": self.suite,
            "api_pack": api_pack,
            "target_url": self.target_url,
            "login_mode": self.login_mode,
            "soak_min": self.soak_min,
            "skip_ui": self.skip_ui,
            "skip_sheet": self.skip_sheet,
            "skip_drive": self.skip_drive,
            "skip_cliq": self.skip_cliq,
            "fixtures": self.fixtures,
            "skip_soak": self.soak_min <= 0,
        }


class PendingReleaseStore:
    """Thread-safe pending approvals (JSON file for restart survival)."""

    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        base = Path(os.getenv("QA_AGENT_ARTIFACT_DIR") or Path.cwd() / "artifacts" / "releases")
        self._path = path or (base / "_pending_cliq_approvals.json")
        self._items: dict[str, PendingReleaseRequest] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for rid, row in (raw or {}).items():
                self._items[rid] = PendingReleaseRequest(**row)
        except Exception:  # noqa: BLE001
            self._items = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v.to_dict() for k, v in self._items.items()}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create(self, **kwargs: Any) -> PendingReleaseRequest:
        request_id = str(kwargs.pop("request_id", None) or f"relreq-{uuid.uuid4().hex[:12]}")
        req = PendingReleaseRequest(
            request_id=request_id,
            admin=release_admin(),
            tracking_id=str(kwargs.pop("tracking_id", None) or f"qa-{uuid.uuid4().hex[:12]}"),
            **kwargs,
        )
        with self._lock:
            self._items[request_id] = req
            self._save()
        return req

    def get(self, request_id: str) -> PendingReleaseRequest | None:
        with self._lock:
            return self._items.get(request_id)

    def update(self, request_id: str, **fields: Any) -> PendingReleaseRequest | None:
        with self._lock:
            req = self._items.get(request_id)
            if not req:
                return None
            for k, v in fields.items():
                if hasattr(req, k):
                    setattr(req, k, v)
            req.updated_at = _utc()
            self._save()
            return req


_STORE: PendingReleaseStore | None = None


def get_pending_store() -> PendingReleaseStore:
    global _STORE
    if _STORE is None:
        _STORE = PendingReleaseStore()
    return _STORE


def build_cliq_approval_body(req: PendingReleaseRequest) -> str:
    base = gateway_public_base()
    approve_tok = sign_request(req.request_id, "approve")
    reject_tok = sign_request(req.request_id, "reject")
    admin = req.admin or release_admin() or "(set QA_AGENT_RELEASE_ADMIN)"
    q_approve = urlencode(
        {"token": approve_tok, "actor": admin, "notes": "approved_via_cliq"}
    )
    q_reject = urlencode(
        {"token": reject_tok, "actor": admin, "notes": "rejected_via_cliq"}
    )
    approve_url = f"{base}/v2/releases/{quote(req.request_id)}/approve?{q_approve}"
    reject_url = f"{base}/v2/releases/{quote(req.request_id)}/reject?{q_reject}"
    return "\n".join(
        [
            f"Asrax RELEASE APPROVAL — {req.release_name or req.release_id or req.request_id}",
            f"request_id: {req.request_id}",
            f"env: {req.env} | suite: {req.suite} | soak: {req.soak_min}m",
            f"url: {req.target_url}",
            f"requested_by: {req.requested_by or 'n/a'}",
            "",
            f"Approver (ONLY this person): {admin}",
            "One confirmation starts AsraxReleaseOpsWorkflow (UI pack + soak + Sheet/Drive + Cliq final).",
            "",
            f"APPROVE (admin only): {approve_url}",
            f"REJECT: {reject_url}",
            "",
            "Or reply in this chat: approve <request_id>   /   reject <request_id>",
            "(Cliq bot must POST /webhooks/cliq/release with actor = admin)",
        ]
    )


def build_cliq_started_body(req: PendingReleaseRequest) -> str:
    return "\n".join(
        [
            f"Asrax RELEASE STARTED — {req.release_name or req.release_id or req.request_id}",
            f"approved_by: {req.decision_actor}",
            f"workflow_id: {req.workflow_id}",
            f"tracking_id: {req.tracking_id}",
            f"Temporal: AsraxReleaseOpsWorkflow",
            "Trace phases: init → ui_suite → pack_t0 → soak → score → sheet → drive → cliq_final",
        ]
    )


_APPROVE_RE = re.compile(r"\b(approve|confirm|go|start)\b", re.I)
_REJECT_RE = re.compile(r"\b(reject|deny|cancel|no)\b", re.I)
_REQ_RE = re.compile(r"(relreq-[a-f0-9]{8,}|asrax-r01-[\w-]+)", re.I)


def parse_cliq_chat_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Cliq bot / Deluge / link-click payloads into action + actor + request_id."""
    message = (
        payload.get("message")
        or payload.get("text")
        or (payload.get("data") or {}).get("message")
        or ""
    )
    if isinstance(message, dict):
        message = str(message.get("text") or message.get("content") or "")
    message = str(message).strip()

    actor_raw = payload.get("actor") or payload.get("user") or payload.get("user_id") or payload.get("email")
    if isinstance(actor_raw, dict):
        actor = str(actor_raw.get("email") or actor_raw.get("id") or actor_raw.get("name") or "")
    else:
        actor = str(actor_raw or "").strip()

    action = str(payload.get("action") or "").strip().lower()
    request_id = str(payload.get("request_id") or payload.get("id") or "").strip()
    token = str(payload.get("token") or "").strip()

    if not action and message:
        if _APPROVE_RE.search(message):
            action = "approve"
        elif _REJECT_RE.search(message):
            action = "reject"
    if not request_id and message:
        m = _REQ_RE.search(message)
        if m:
            request_id = m.group(1)

    return {
        "action": action,
        "request_id": request_id,
        "actor": actor,
        "token": token,
        "notes": str(payload.get("notes") or message or "")[:500],
        "raw_message": message,
    }
