# Phase 19 — Canonical Geometry Contract

Status: S7 contract layer delivered; consumer wiring and infrastructure verification remain.

## Authority

`CAD_BREP` is the only authoritative geometry source for engineering and user-facing 3D output. `LEGACY_IR` is non-authoritative and must never be used as a fallback for engineering, quantities, structural/regulatory assessment, validation, or persisted presentation geometry.

Authoritative CAD also requires current World Model/design hashes, a successful CAD run, and explicit validation evidence. Source labeling alone is insufficient.

## Canonical dependency chain

`World Model + Design → CAD B-rep → Quantity → Structural / Regulatory → Validation / Evidence → Cost`

Each stage must carry the exact upstream hashes needed to reproduce or invalidate its result. Missing provenance is a hard failure, not an implicit dependency.

## Staleness

A geometry artifact is stale whenever its recorded World Model or design hash differs from the current input. Stale geometry remains historical evidence but is not eligible for current consumption.

## Phase 19 acceptance

The repository now has reusable contracts for:

- geometry authority and canonical identity;
- CAD-run validation evidence;
- geometry staleness and dependency reasons;
- quantity, structural, regulatory, and cost provenance;
- whole-chain Phase 19 acceptance.

These contracts are deliberately deterministic and fail closed. They do not certify geometry, structural adequacy, regulatory compliance, or construction readiness.

## Remaining implementation gates

1. Wire the contracts into every authoritative consumer and persistence boundary.
2. Remove remaining direct legacy GeometryIR execution paths from authoritative code.
3. Replace remaining IR-only fixtures with CAD-like measured fixtures.
4. Prove stale propagation during concurrent CAD generation and downstream regeneration.
5. Verify PostgreSQL/PostGIS, real CAD-worker/toolchain execution, tenant isolation, downloads, and complete GitHub Actions CI on the final release head.
