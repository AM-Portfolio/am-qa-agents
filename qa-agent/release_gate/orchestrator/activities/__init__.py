"""Temporal activity registration — domain modules (not numbered phases).

Modules:
  intake      — classify, LoadContext, index await, fin prep, notify
  testing     — ChangeIntent, matrix plan/execute, handoff, episodes
  evidence    — observe comparisons, post-test verify, analysis, PDF dossier
  governance  — SAST, HITL gate, GitHub checks, learning / promotion
"""

from orchestrator.activities.intake import (
    activity_await_index,
    activity_classify,
    activity_fin_data_prep,
    activity_notify,
    activity_resolve_load_profile,
    activity_smoke_ui_test,
)
from orchestrator.activities.evidence import (
    activity_analyze_release,
    activity_collect_comparisons,
    activity_post_test_verify,
    activity_publish_pdf,
    build_evidence_bundle,
)
from orchestrator.activities.testing import (
    activity_build_test_matrix,
    activity_dev_handoff_stub,
    activity_dev_handoff_ticket,
    activity_ensure_catalog_ready,
    activity_execute_matrix,
    activity_interpret_change_intent,
    activity_persist_episode,
)
from orchestrator.activities.governance import (
    activity_await_release_hitl,
    activity_evaluate_learning,
    activity_github_check_run,
    activity_ingest_hitl_feedback,
    activity_record_promotion,
    activity_security_scan,
)
from orchestrator.activities.release_ops import (
    activity_release_ops_cliq_final,
    activity_release_ops_complete,
    activity_release_ops_init,
    activity_release_ops_pack_t0,
    activity_release_ops_publish_drive,
    activity_release_ops_publish_sheet,
    activity_release_ops_stability_score,
    activity_release_ops_ui_suite,
)

__all__ = [
    "activity_await_index",
    "activity_classify",
    "activity_dev_handoff_stub",
    "activity_dev_handoff_ticket",
    "activity_fin_data_prep",
    "activity_notify",
    "activity_resolve_load_profile",
    "activity_smoke_ui_test",
    "activity_collect_comparisons",
    "activity_post_test_verify",
    "activity_analyze_release",
    "activity_publish_pdf",
    "activity_interpret_change_intent",
    "activity_build_test_matrix",
    "activity_ensure_catalog_ready",
    "activity_execute_matrix",
    "activity_persist_episode",
    "activity_security_scan",
    "activity_await_release_hitl",
    "activity_github_check_run",
    "activity_ingest_hitl_feedback",
    "activity_evaluate_learning",
    "activity_record_promotion",
    "activity_release_ops_init",
    "activity_release_ops_ui_suite",
    "activity_release_ops_pack_t0",
    "activity_release_ops_stability_score",
    "activity_release_ops_publish_sheet",
    "activity_release_ops_publish_drive",
    "activity_release_ops_cliq_final",
    "activity_release_ops_complete",
    "build_evidence_bundle",
]
