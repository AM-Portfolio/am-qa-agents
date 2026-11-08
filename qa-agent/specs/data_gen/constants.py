"""Shared constants for am-specs data-gen ↔ Specs bridge."""
from __future__ import annotations

# User-facing suite → disk profile under .generated/.../profiles/<profile>/
SUITE_TO_PROFILE: dict[str, str] = {
    "default": "prod",
    "working": "prod",
    "prod": "prod",
    "full": "full",
    "premium": "premium",
}

# Primary SPT row preference (higher = preferred)
CASE_KIND_PRIORITY: dict[str, int] = {
    "must_work": 100,
    "happy": 80,
    "cross_flow": 60,
    "crud": 50,
    "validation_error": 40,
    "technical": 20,
}

SUITE_CASE_KINDS: dict[str, frozenset[str]] = {
    "default": frozenset({"happy", "must_work"}),
    "working": frozenset({"happy", "must_work"}),
    "full": frozenset({"happy", "must_work", "technical"}),
    "premium": frozenset(
        {
            "happy",
            "must_work",
            "technical",
            "validation_error",
            "crud",
            "business",
        }
    ),
}

# Cross_flow never selected for k6 — workflows only
WORKFLOW_GROUP = "data_gen"
WORKFLOW_SOURCE_TAG = "am-specs-data-gen"

PAYLOAD_SET_LABEL_PREFIX = "data-gen-"
