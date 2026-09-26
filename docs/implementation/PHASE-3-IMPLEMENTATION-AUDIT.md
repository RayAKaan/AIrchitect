# Phase 3 Implementation Audit

**Date:** 2026-09-25  
**Status:** source audit complete before Phase 3 implementation

## Reusable canonical interfaces

- `resolve_project_version(...)` enforces authenticated tenant/project/version resolution and must remain the entry point.
- `resolve_world_model(...)` returns the exact persisted canonical `WorldModelRevision`.
- Phase 2 `DesignAlternative` and `GeometryArtifact` already retain world/design/geometry hashes, statuses, provenance, versions, and project-version ownership.
- `GeometryArtifact.payload_json.geometry_ir` is the sole authoritative geometric input for Phase 3.
- `ArtifactVersion`, `ArtifactDependency`, and `new_artifact(...)` are the existing lineage graph and will be reused.
- `audit(...)`, structured logging, canonical JSON hashing, existing status/error conventions, and native authentication will be reused.
- The Phase 2 Design workspace and TanStack Query client are the frontend integration point.

## Existing Phase 0/1 engineering entities

The schema already contains minimal `QuantityArtifact`, `RateSchedule`, `CostEstimate`, `StructuralArtifact`, `RegulatoryRuleset`, `RegulatoryRule`, `RegulatoryEvaluation`, `ValidationRun`, and `ValidationCheck` tables. They are sparse but are the correct entities to evolve. They will not be duplicated.

Legacy public estimate/structure/regulatory/validation utilities accept caller-authored numerical facts and therefore cannot serve as authoritative Phase 3 calculation routes. They may remain for compatibility, but new Phase 3 version-scoped routes will resolve persisted inputs server-side.

The old integrated lifecycle pipeline predates Phase 2 and generates its own alternatives/geometry/quantities. It is not suitable as the Phase 3 source chain and will not be invoked by the new implementation. Phase 3 will bind only to the Phase 2 artifacts.

## Required extensions

- Expand the existing engineering entities with relational source IDs, exact input hashes, independent engine/config versions, output hashes, lifecycle status, assumptions/unknowns/uncertainty/provenance, and timestamps.
- Add normalized rate entries and regulatory results while retaining JSON payloads for rich immutable calculation records.
- Add deterministic quantity, cost, structural, regulatory, and cross-artifact validation engines.
- Add version/alternative-scoped calculation and retrieval APIs with idempotency and stale propagation.
- Extend the Design workspace with Quantities, Cost, Structure, Regulations, Validation, provenance, uncertainty, and comparison fields.

## Safety decisions

- No Saudi market rate will be seeded or implied. With no selected schedule, cost returns `COST_UNAVAILABLE`.
- User-provided schedules are explicitly labeled `USER_PROVIDED`; demo schedules are explicitly `DEMO`.
- No Saudi rule thresholds will be invented. The built-in provider supplies declared no-rule checks yielding `UNKNOWN` with explicit reason/provenance.
- Structure remains a deterministic preliminary concept only. Soil-dependent foundation classification remains `UNKNOWN` without soil data.
- Concrete, reinforcement, MEP, finishes, and other unsupported detailed quantities remain `NOT_SUPPORTED`.
- Phase 3 artifacts never mutate the World Model, alternative, or Geometry IR.

## Migration strategy

Create revision `20260925_0004`, evolving existing tables with SQLite batch operations and legacy-safe defaults. Preserve old rows as `ARCHIVED`/legacy where exact source hashes are absent. Add indexes and uniqueness constraints for deterministic identity.

## Verification plan

Focused pure-engine tests; persistence/API/tenant/idempotency/staleness/multiversion tests; fresh and legacy SQLite migration cycles; full Phase 1/2 regression suite; TypeScript/Vitest/build; real Chromium E2E; and manual screenshot inspection. PostgreSQL remains explicitly NOT RUN unless actually available.
