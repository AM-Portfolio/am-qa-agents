"""Format registry for collection adapters."""
from __future__ import annotations

from typing import Any

from specs.import_adapters.base import CollectionAdapter
from specs.import_adapters.postman_v2 import PostmanV2Adapter

_ADAPTERS: list[CollectionAdapter] = [
    PostmanV2Adapter(),
]


def list_formats() -> list[str]:
    return [a.format_id for a in _ADAPTERS]


def get_adapter(format_id: str | None = None, *, raw: Any = None) -> CollectionAdapter:
    if format_id:
        fid = format_id.strip().lower()
        for a in _ADAPTERS:
            if a.format_id == fid:
                return a
        raise ValueError(f"Unsupported import format: {format_id}. Known: {list_formats()}")
    if raw is not None:
        for a in _ADAPTERS:
            if a.detect(raw):
                return a
    # Default Postman for explicit UI uploads
    return _ADAPTERS[0]
