"""Prometheus metrics — /metrics on gateway."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Any


class _Counter:
    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help = help_text
        self._vals: dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def inc(self, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._vals[key] += 1

    def render(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        with self._lock:
            for key, val in self._vals.items():
                if key:
                    label = ",".join(f'{k}="{v}"' for k, v in key)
                    lines.append(f"{self.name}{{{label}}} {val}")
                else:
                    lines.append(f"{self.name} {val}")
        return "\n".join(lines)


class _HistogramLite:
    """Simple latency sum/count (not full Prometheus histogram buckets)."""

    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help = help_text
        self._sum: dict[tuple, float] = defaultdict(float)
        self._count: dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def observe(self, seconds: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._sum[key] += seconds
            self._count[key] += 1

    def render(self) -> str:
        lines = [f"# HELP {self.name}_seconds {self.help}", f"# TYPE {self.name}_seconds summary"]
        with self._lock:
            for key in set(self._sum) | set(self._count):
                label = ",".join(f'{k}="{v}"' for k, v in key) if key else ""
                prefix = f"{self.name}_seconds{{{label}}}" if label else f"{self.name}_seconds"
                lines.append(f"{prefix}_sum {self._sum[key]}")
                lines.append(f"{prefix}_count {self._count[key]}")
        return "\n".join(lines)


RUNS = _Counter("qa_agent_runs_total", "Release readiness runs by route/status")
GNX = _Counter("qa_agent_gnx_mode_total", "Runs by gnx_mode")
LLM = _Counter("qa_agent_llm_calls_total", "Gated LLM calls")
HITL = _Counter("qa_agent_hitl_total", "HITL decisions")
PHASE = _HistogramLite("qa_agent_phase_latency", "Phase latency seconds")


def mark_run(*, route: str, status: str, gnx_mode: str | None = None) -> None:
    RUNS.inc(route=route or "unknown", status=status or "unknown")
    if gnx_mode:
        GNX.inc(mode=gnx_mode)


def mark_hitl(decision: str) -> None:
    HITL.inc(decision=decision or "unknown")


def mark_llm(prompt: str) -> None:
    LLM.inc(prompt=prompt or "unknown")


def render_metrics() -> str:
    return "\n".join([RUNS.render(), GNX.render(), LLM.render(), HITL.render(), PHASE.render()]) + "\n"
