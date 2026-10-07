"""ServiceOnboardPrepWorkflow — Specs prep phases with structured per-step failure report."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestrator.activities.onboard_prep import (
        activity_onboard_analyze,
        activity_onboard_apis,
        activity_onboard_auth,
        activity_onboard_contract,
        activity_onboard_generate_payloads,
        activity_onboard_llm_status,
        activity_onboard_openapi_sync,
        activity_onboard_overview,
        activity_onboard_persist_report,
        activity_onboard_prepare_mcp,
        activity_onboard_tools_refresh,
        activity_onboard_tools_smoke,
    )
    from orchestrator.activities.onboard_report import build_report, normalize_env


@workflow.defn(name="ServiceOnboardPrepWorkflow")
class ServiceOnboardPrepWorkflow:
    """End-to-end Specs onboard prep for one service/env."""

    @workflow.run
    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        retry = RetryPolicy(maximum_attempts=2)
        short = timedelta(minutes=15)
        long = timedelta(minutes=45)
        wf_id = workflow.info().workflow_id
        service = str(args.get("service") or "").strip()
        env = normalize_env(args.get("environment"))
        base = {**args, "service": service, "environment": env, "workflow_id": wf_id}

        def _phase(phase: str, detail: str = "") -> None:
            msg = (
                f"flow.phase={phase} workflow_id={wf_id} service={service} env={env}"
            )
            if detail:
                msg += f" {detail}"
            workflow.logger.info(msg)

        steps: list[dict[str, Any]] = []
        warnings: list[str] = []
        payload_set_version: int | None = None
        tool_count: int | None = None
        api_count: int | None = None
        llm_rows = 0
        target_url = ""

        async def _run(phase: str, fn, payload: dict[str, Any], *, timeout=short) -> dict[str, Any]:
            _phase(phase)
            step = await workflow.execute_activity(
                fn,
                payload,
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )
            steps.append(step)
            _phase(phase, f"ok={step.get('ok')} status={step.get('status')}")
            return step

        # analyze
        step = await _run("analyze", activity_onboard_analyze, base)
        if step.get("hard_fail") or not step.get("ok"):
            return await self._finish(
                service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
            )
        target_url = str((step.get("evidence") or {}).get("target_url") or "")

        step = await _run(
            "openapi_sync",
            activity_onboard_openapi_sync,
            {**base, "target_url": target_url},
        )
        if step.get("hard_fail") or not step.get("ok"):
            return await self._finish(
                service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
            )

        step = await _run("apis_catalog", activity_onboard_apis, base)
        if step.get("hard_fail") or not step.get("ok"):
            return await self._finish(
                service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
            )
        api_count = (step.get("evidence") or {}).get("api_count")

        step = await _run("tools_refresh", activity_onboard_tools_refresh, base)
        if step.get("hard_fail") or not step.get("ok"):
            return await self._finish(
                service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
            )
        tool_count = (step.get("evidence") or {}).get("tool_count")

        step = await _run("contract", activity_onboard_contract, base)
        if step.get("hard_fail") or not step.get("ok"):
            return await self._finish(
                service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
            )

        step = await _run("auth_try_token", activity_onboard_auth, base)
        if step.get("hard_fail") or not step.get("ok"):
            return await self._finish(
                service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
            )

        step = await _run("prepare_mcp", activity_onboard_prepare_mcp, base)
        if not step.get("ok") or str(step.get("status") or "").startswith("warn"):
            if step.get("error") or str(step.get("status") or "").startswith("warn"):
                warnings.append(f"prepare_mcp:{step.get('status')}")

        step = await _run(
            "generate_all_payloads",
            activity_onboard_generate_payloads,
            base,
            timeout=long,
        )
        ev = step.get("evidence") or {}
        if ev.get("payload_set_version") is not None:
            payload_set_version = int(ev["payload_set_version"])
        llm_rows = int(ev.get("llm_rows") or 0)
        if step.get("hard_fail") or (not step.get("ok") and step.get("required")):
            return await self._finish(
                service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
            )
        if not step.get("ok"):
            warnings.append(f"generate_all_payloads:{step.get('status')}")

        step = await _run(
            "llm_fallback",
            activity_onboard_llm_status,
            {**base, "llm_rows": llm_rows},
        )
        if str(step.get("status") or "") not in {"ok", "skipped_allow_llm_false"}:
            warnings.append(f"llm_fallback:{step.get('status')}")

        step = await _run("tools_smoke", activity_onboard_tools_smoke, base)
        if step.get("hard_fail"):
            return await self._finish(
                service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
            )
        if step.get("status") in {"billing_dependency", "smoke_soft_failure"}:
            warnings.append(f"tools_smoke:{step.get('status')}")

        await _run(
            "overview_report",
            activity_onboard_overview,
            {**base, "warnings": warnings},
        )

        return await self._finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count, args
        )

    async def _finish(
        self,
        service: str,
        env: str,
        wf_id: str,
        steps: list[dict[str, Any]],
        warnings: list[str],
        payload_set_version: int | None,
        tool_count: int | None,
        api_count: int | None,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        report = build_report(
            service=service,
            environment=env,
            workflow_id=wf_id,
            steps=steps,
            payload_set_version=payload_set_version,
            tool_count=tool_count,
            api_count=api_count,
            warnings=warnings,
            mode=str(args.get("mode") or "temporal"),
        )
        try:
            await workflow.execute_activity(
                activity_onboard_persist_report,
                {"report": report, "service": service, "environment": env},
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
        except Exception:  # noqa: BLE001 — report still returned
            workflow.logger.warning("flow.phase=persist_report failed workflow_id=%s", wf_id)
        return report
