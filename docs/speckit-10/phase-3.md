# Phase 3 — Next wave (after am-market Grown)

**Goal:** Only after [phase-2.md](phase-2.md) market pilot is Grown — generate + E2E for the next service wave. Steady-state remains **change-driven** ([PIPELINE.md](PIPELINE.md)).

**Prereq:** Phase 2 **am-market** Grown (all three E2E GO).

**Owner:** SpecKit orchestrates; generators in **am-specs**.

## Next-wave set (this phase)

`am-portfolio`, `am-oms`, `am-trade-management-service`, `am-analysis`, `am-document-processor`, `am-cloudinary-manager`, `am-email-extractor`, `am-identity`

(Remaining enabled catalog → Phase 4 / later.)

## Implement

- [ ] Confirm Phase 2 Grown (market-data, news, parser)
- [ ] Backfill typed SDK + MCP per next-wave id (batched PRs or dispatch)
- [ ] E2E per service: contract + Java + Python + Dart + MCP
- [ ] Update [INVENTORY.md](INVENTORY.md)
- [ ] GitHub MCP: validate + e2e green

## Test

Use [tests/phase-3.md](tests/phase-3.md).

- [ ] No next-wave work started before market Grown
- [ ] Each next-wave service typed + E2E GO
- [ ] Change-driven still holds

## Grown

- [ ] Next wave green; ready for Phase 4 (SpecKit hardening + remaining fleet)

## Stop if fail

Any next-wave E2E fail → fix before Phase 4 fleet.

## Refuse

- No skipping market pilot
- No full-fleet regenerate as default on every merge
