# ADR-QA-004 — PDF dossier store

## Status

Accepted

## Context

Approvers need a durable release dossier (HTML/PDF) with comparisons and recommendation before `approve.release`.

## Decision

Render HTML in qa-agent (weasyprint optional). Phase 0–4: **local `artifacts/pdf`**. Production path: tool-agent `document.store` → MinIO. PDF link is required on HITL card.

## Consequences

- Inline local runs always produce HTML even without weasyprint
- Store backend is config (`pdf.store_via`)
