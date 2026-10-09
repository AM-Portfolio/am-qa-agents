"""Pack/unpack JSON payload documents as .zip (or gzip) for faster transfer."""

from __future__ import annotations

import base64
import gzip
import io
import json
import zipfile
from typing import Any


DEFAULT_MEMBER = "payload.json"


class ZipCodecError(ValueError):
    """Invalid or empty zip/gzip/json payload blob."""


def dumps_json_bytes(doc: Any) -> bytes:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"), default=str).encode(
        "utf-8"
    )


def loads_json_bytes(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ZipCodecError(f"invalid JSON payload: {exc}") from exc


def pack_zip(doc: Any, *, member: str = DEFAULT_MEMBER) -> bytes:
    """Return a zip archive containing one JSON member (best for large payload sets)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, dumps_json_bytes(doc))
    return buf.getvalue()


def pack_gzip(doc: Any) -> bytes:
    return gzip.compress(dumps_json_bytes(doc), compresslevel=6)


def _first_json_member(zf: zipfile.ZipFile) -> bytes:
    names = [n for n in zf.namelist() if not n.endswith("/") and not n.startswith("__MACOSX")]
    if not names:
        raise ZipCodecError("zip has no files")
    preferred = [
        n
        for n in names
        if n.lower().endswith(".json")
        or n.lower() in {DEFAULT_MEMBER, "import_body.json", "payload_set.json"}
    ]
    pick = preferred[0] if preferred else names[0]
    return zf.read(pick)


def unpack_blob(raw: bytes, *, filename: str | None = None) -> Any:
    """Decode zip, gzip, or raw JSON bytes into a Python object."""
    if not raw:
        raise ZipCodecError("empty blob")
    name = (filename or "").lower()
    # ZIP magic
    if raw[:2] == b"PK" or name.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                return loads_json_bytes(_first_json_member(zf))
        except zipfile.BadZipFile as exc:
            raise ZipCodecError(f"invalid zip: {exc}") from exc
    # gzip magic
    if raw[:2] == b"\x1f\x8b" or name.endswith((".gz", ".gzip")):
        try:
            return loads_json_bytes(gzip.decompress(raw))
        except OSError as exc:
            raise ZipCodecError(f"invalid gzip: {exc}") from exc
    return loads_json_bytes(raw)


def unpack_b64(b64: str, *, filename: str | None = None) -> Any:
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ZipCodecError(f"invalid base64: {exc}") from exc
    return unpack_blob(raw, filename=filename)


def maybe_expand_import_fields(body: dict[str, Any]) -> dict[str, Any]:
    """Expand zip_b64 / gzip_b64 / payload_zip_b64 onto payload_set/collection.

    Mutates a shallow copy. Prefer zip when both JSON and zip are present.
    """
    out = dict(body)
    b64 = (
        out.pop("zip_b64", None)
        or out.pop("payload_zip_b64", None)
        or out.pop("gzip_b64", None)
    )
    if not b64:
        return out
    fname = str(out.pop("zip_filename", None) or "payload.zip")
    if out.get("gzip_b64") is None and "gzip" in fname.lower():
        pass
    doc = unpack_b64(str(b64), filename=fname)
    if not isinstance(doc, dict):
        raise ZipCodecError("zip JSON root must be an object")
    # data-gen import_body shape
    if "payload_set" in doc or "collection" in doc or "service" in doc:
        for k in ("payload_set", "collection", "env", "environment", "profile", "label", "format"):
            if k in doc and out.get(k) is None:
                out[k] = doc[k]
        if out.get("service") is None and doc.get("service"):
            out["service"] = doc["service"]
        # whole doc is the payload_set itself
        if out.get("payload_set") is None and "apis" in doc:
            out["payload_set"] = doc
        return out
    if "apis" in doc:
        out.setdefault("payload_set", doc)
        return out
    out.setdefault("collection", doc)
    return out
