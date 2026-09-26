# Phase 2 implementation audit

Date: 2026-09-25

## Existing Phase 1 capability

- Native email/password authentication, organization memberships and non-disclosing tenant resolution.
- Transactional Project -> V1 -> typed World Model creation.
- Immutable ProjectVersion lifecycle with canonical `current_version_id`, optimistic `revision_number`, parent lineage and idempotent version creation.
- Canonical building briefs, persisted typed requirements, explicit assumptions, provenance, audit events, deterministic World Model hashing, snapshots and semantic comparison.
- Central `resolve_project_version(...)` and hash-verifying `resolve_world_model(...)` services.
- Alembic-only schema management; current head before this pass: `20260925_0002`.
- React/TypeScript/Vite workspace, TanStack Query provider, Three.js/R3F/Drei dependencies, and a Phase 1 Building Brain workspace.

## Reusable Phase 1 interfaces

- `app.domains.foundation.service.resolve_project_version`
- `app.domains.foundation.service.resolve_world_model`
- `app.domains.foundation.service.audit`
- `app.domains.lifecycle.service.canonical_hash`
- `ArtifactVersion` and `ArtifactDependency`
- Existing `DesignAlternative` and `GeometryArtifact` tables (extended rather than replaced)
- Existing native auth and membership dependencies
- Existing request-ID/error envelope

## Existing schema and conflicts

The repository already had prototype alternatives/geometry tables and a deterministic cuboid engine. They were tied to a later-phase monolithic feasibility service and lacked constraints, strategy/version fields, generation runs, explicit design hashes, selection provenance, typed Geometry IR and sufficient validation. The unsafe direct `/geometry/generate` route had already been disabled in Phase 1. The old R3F viewer interpreted a legacy vertices/faces payload and was no longer the active Phase 1 workspace.

Potential conflicts addressed by this pass:

- do not create duplicate alternative/geometry architectures;
- preserve old columns for compatibility while extending the entities;
- use World Model resolution rather than client dimensions;
- keep Three.js types out of the backend domain;
- do not mark V1 artifacts stale merely because V2 exists;
- distinguish staleness caused by a changed World Model hash within the same version;
- keep structural grids explicitly preliminary;
- do not fabricate parking layouts, site orientation, setbacks or regulatory results.

## Existing API conventions

Version-scoped APIs use `/api/v1/projects/{project_id}/versions/{version_ref}/...`, accept UUID or numeric version references, enforce tenant membership through the central resolver and return structured errors with request IDs. Phase 2 follows this convention.

## Existing frontend architecture

The frontend is a compact React application. Project opening enters `FoundationWorkspace`; feature code exists under `src/features`. Phase 2 should add a feature-oriented `design` workspace, reuse the current project/version context and TanStack Query provider, and translate persisted Geometry IR into R3F scene objects.

## Existing testing conventions

- pytest + async SQLite API integration fixtures;
- deterministic service unit tests;
- Ruff;
- Vitest pure view-model tests;
- Alembic empty-database migration cycle;
- PostGIS/PostgreSQL migration cycle configured in CI but unavailable locally.

Pre-change Phase 2 baseline executed:

- backend: 79 passed;
- Ruff: passed;
- frontend: 3 Vitest tests passed, TypeScript/build passed;
- migration cycle through `20260925_0002`: passed on SQLite;
- PostgreSQL: unavailable locally (`docker`, `psql`, and `pg_isready` absent).

## Phase 2 integration points

1. Resolve committed version and canonical World Model.
2. Resolve and persist design constraints with source references.
3. Build a versioned deterministic search space/config.
4. Generate candidates through Balanced, Compact and Low-Rise strategies.
5. Validate and deduplicate candidates.
6. Persist alternative artifact versions linked to exact World Model revision/hash.
7. Generate typed Geometry IR and validate it.
8. Persist geometry artifact versions with explicit alternative dependencies.
9. Expose version-scoped list/detail/geometry/comparison/selection APIs.
10. Render exact Geometry IR in a dedicated R3F design workspace.

## Required migration

A new `20260925_0003` revision is required to add generation runs, constraints, indexes/uniqueness, strategy/hash/provenance/selection fields on alternatives, and engine/hash/status fields on geometry artifacts.

## Required new modules

- `app/domains/design/constraints.py`
- `app/domains/design/config.py`
- `app/domains/design/strategies.py`
- `app/domains/design/geometry_ir.py`
- `app/domains/design/engine.py`
- `app/domains/design/routes.py`
- Phase 2 backend tests and fixtures
- `apps/web/src/features/design/*`

No Phase 3 quantity/cost/structural/regulatory implementation is part of this pass.
