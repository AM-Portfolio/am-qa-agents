"""Temporal worker entrypoint."""

from __future__ import annotations

from am_qa_agent.env_bootstrap import load_env

load_env()

import asyncio
import os

from am_qa_agent.orchestrator.queue import (
    assert_safe_task_queue,
    resolve_namespace,
    resolve_task_queue,
)


async def run_worker() -> None:
    from temporalio.client import Client
    from temporalio.worker import Worker
    from temporalio.worker.workflow_sandbox import (
        SandboxedWorkflowRunner,
        SandboxRestrictions,
    )

    from am_qa_agent.orchestrator.activities import (
        activity_analyze_release,
        activity_await_index,
        activity_await_release_hitl,
        activity_build_test_matrix,
        activity_classify,
        activity_collect_comparisons,
        activity_dev_handoff_ticket,
        activity_evaluate_learning,
        activity_execute_matrix,
        activity_fin_data_prep,
        activity_github_check_run,
        activity_ingest_hitl_feedback,
        activity_interpret_change_intent,
        activity_notify,
        activity_persist_episode,
        activity_post_test_verify,
        activity_publish_pdf,
        activity_record_promotion,
        activity_resolve_load_profile,
        activity_security_scan,
        activity_smoke_ui_test,
    )
    from am_qa_agent.orchestrator.workflows import ReleaseReadinessWorkflow

    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = resolve_namespace()
    queue = assert_safe_task_queue()
    client = await Client.connect(host, namespace=namespace)
    # Workflow still does light ledger upserts around HITL; pass through am_qa_agent.
    runner = SandboxedWorkflowRunner(
        restrictions=SandboxRestrictions.default.with_passthrough_modules(
            "am_qa_agent",
        )
    )
    worker = Worker(
        client,
        task_queue=queue,
        workflows=[ReleaseReadinessWorkflow],
        activities=[
            activity_classify,
            activity_resolve_load_profile,
            activity_await_index,
            activity_security_scan,
            activity_interpret_change_intent,
            activity_build_test_matrix,
            activity_fin_data_prep,
            activity_execute_matrix,
            activity_smoke_ui_test,
            activity_collect_comparisons,
            activity_post_test_verify,
            activity_analyze_release,
            activity_publish_pdf,
            activity_await_release_hitl,
            activity_persist_episode,
            activity_ingest_hitl_feedback,
            activity_evaluate_learning,
            activity_record_promotion,
            activity_github_check_run,
            activity_notify,
            activity_dev_handoff_ticket,
        ],
        workflow_runner=runner,
    )
    print(f"qa-agent worker listening on queue={queue} host={host} ns={namespace}", flush=True)
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
