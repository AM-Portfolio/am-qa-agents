# ADR-QA-003 — ChangeIntent advisory-only

## Status

Accepted

## Context

LLM synthesis of PR/commits helps humans and dossier narrative, but must not silently expand P0 release blockers.

## Decision

**ChangeIntent is advisory.** Matrix ranking SoT remains GitNexus facts + `load-rules.yaml`. Advisory boost may raise score only when aligned; **never alone creates P0.**

## Consequences

- Deterministic ranker stays reviewable
- Intent still enriches PDF / HITL / ui specification NL
