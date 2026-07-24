# ADR-QA-002 — Degraded release policy

## Status

Accepted

## Context

When GitNexus is down, release readiness can still run smoke, but auto-approval would be unsafe.

## Decision

**Warn + HITL banner** by default (`warn_on_gnx_degraded`). Optional `block_release_if_gnx_down` per env. **Auto-approve is disabled when `gnx_mode=degraded`.**

## Consequences

- Approvers always see degraded banner + PDF
- Smoke floor matrix applies (L3)
