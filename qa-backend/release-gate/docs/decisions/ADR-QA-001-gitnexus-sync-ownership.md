# ADR-QA-001 — GitNexus sync ownership

## Status

Accepted

## Context

qa-agent needs a fresh graph index before impact ranking, but owning `gitnexus analyze` / Jobs duplicates code-intelligence and per-repo CronJobs.

## Decision

**qa-agent never owns sync/analyze.** It only **requests** (optional Job trigger URL) and **awaits** readiness, then queries MCP. Fallback L1–L3 when degraded.

## Consequences

- Single owner for index freshness: code-intelligence / per-repo Jobs
- qa-agent must tolerate degraded mode and surface banners on HITL/PDF
