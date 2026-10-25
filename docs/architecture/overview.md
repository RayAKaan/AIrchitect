# AIrchitect Architecture Overview

**Status:** repository truth on `main` after the S1 Site World Model / Site Workspace completion merge.

This document describes what exists today. Planned roadmap capabilities are explicitly marked as planned and must not be treated as implemented.

## Product boundary

AIrchitect is a modular-monolith, AI-assisted architectural feasibility and design workspace. The current implementation is strongest in project/version management, requirements and assumptions, the persisted World Model, the complete S1 Site World Model / Site Workspace, artifact versioning/dependencies, design generation, geometry/CAD infrastructure, change-impact propagation, validation, and the React workspace shell. The complete Site → Program → Concepts → Building → Drawings → Analysis → Review → BIM/CAD product is not yet implemented end-to-end.

## S1 — Site World Model / Site Workspace

S1 is complete. The authoritative site layer provides:

- canonical site revisions and the validated `SetSiteBoundary` command with idempotency and stale-base protection;
- EPSG:4326 interchange with a site-local metric calculation CRS;
- manual/map, GeoJSON and KML boundary workflows, with imported geometry remaining a draft until server validation;
- provider catalog, reviewed terms, health/capability gates and fail-closed context fetching;
- persisted context snapshots with provider/dataset/source lineage;
- deterministic site analysis for context, mobility, land use, green/water, figure-ground and solar orientation;
- explicit `UNKNOWN` climate/terrain states when no authoritative provider is bound;
- server-authoritative freshness plus persisted `STALE` lifecycle state for historical derived snapshots and evidence;
- evidence inspection with source, retrieval, dataset, geographic-scope, license and method provenance;
- deterministic SVG diagram generation for figure-ground, movement, land use, green/water and solar/orientation;
- presentation-only board composition, stale-data export gating and onboarding templates;
- browser acceptance coverage for the authenticated site workspace and board workflow.

S1 outputs remain derived projections. A site revision is the source of truth; downstream analysis, diagrams, evidence and presentation artifacts never become canonical site geometry.

## Runtime shape

```text
Browser (React + TypeScript + Vite)
        |
        | HTTP / JSON
        v
FastAPI application
        |
        +--> domain services/routes
        +--> SQLAlchemy persistence
        +--> workflow/task infrastructure
        +--> CAD worker integration
        |
        v
SQLite for development/tests; PostgreSQL/PostGIS is the production direction
```

The backend application entrypoint is `apps/api/app/main.py`. Shared SQLAlchemy models currently live in `apps/api/app/db/models.py`; site persistence is isolated in `apps/api/app/db/site_models.py` because the S1 boundary is now substantial enough to justify a focused persistence module.

## Backend domains currently present

The current `apps/api/app/domains/` tree includes AI, assumptions, CAD, change impact, decisions, design, engineering, estimates, evidence, foundation, geometry, identity, lifecycle, projects, regulatory, requirements, and site. The repository also contains core infrastructure, database configuration, dependencies, and a dedicated CAD worker under `apps/api/app/cad_worker/`.

Domain code should own domain behavior. Routes/adapters should not become alternate sources of truth for canonical state.

## Persistence and canonical state

The current persistence model includes:

- organizations, memberships, projects and project versions;
- building briefs, requirements and assumptions;
- `WorldModelRevision` with a persisted model payload and hash;
- S1 site/site-revision/source/evidence/layer/constraint/observation records;
- `ArtifactVersion` and `ArtifactDependency`;
- design generation runs and constraints;
- workflow/task/event state and audit-oriented records;
- geometry, engineering, estimate, regulatory, evidence and decision records.

The World Model, site revision and versioned artifact/dependency systems are the foundation for canonical-state architecture. UI surfaces may only propose changes; validated domain commands establish canonical state.

## Dependency and change impact

Phase 27 established the authoritative artifact dependency graph and hash-guarded change-impact propagation. It records directed artifact dependencies, detects/guards cycles, propagates staleness, and protects version/project boundaries. Phase 28 added workspace visibility and release validation around that infrastructure. S1 additionally materializes stale site-derived state at the site revision boundary.

This still does **not** constitute the complete dependency-aware regeneration scheduler planned for S3.

## Frontend truth

The current web application is a React/TypeScript/Vite application with a dedicated Site Workspace feature surface. Site state remains server-authoritative; map rendering, evidence inspection, analysis panels, diagrams, boards and onboarding are projections or presentation state.

The target roadmap architecture will continue restructuring the workspace incrementally for Program, Concepts, Building, Drawings, Review and production collaboration.

## API and contracts

The FastAPI application exposes authentication, organization/project, requirements, World Model, artifacts, design, geometry, validation, evidence, workflow, change-impact and S1 site capabilities through domain routes. API contracts are currently represented by FastAPI/Pydantic schemas rather than a generated frontend client. Contract testing and a generated client remain roadmap work.

## Worker model

Persisted task/workflow infrastructure supports task state, events, retries, leases and idempotency. PostgreSQL queue semantics include `SKIP LOCKED` support. CAD processing has a dedicated worker boundary. Expensive future analysis, rendering, export and regeneration work should use the same durable job model rather than blocking HTTP requests.

## Architectural invariants

1. A canonical revision is authoritative; projections and exports are derived.
2. Versioned artifacts retain provenance and dependency lineage.
3. A source revision change may make downstream artifacts stale.
4. AI may interpret/propose; deterministic validation decides whether a proposal can commit.
5. Evidence-backed facts must retain provenance and uncertainty.
6. Tenant/project/version boundaries are enforced at persistence and service boundaries.
7. New domain systems must reuse existing dependency, task, revision and audit infrastructure rather than create parallel equivalents.
8. No document in `docs/architecture/` should imply that a roadmap capability exists unless code and tests demonstrate it.

## Remaining roadmap boundary

- Program, envelope and deterministic concept-generation workflow is incomplete (S2).
- Universal command bus, edit history and runtime regeneration are not yet unified (S3).
- Full semantic building model, unified 2D/3D renderer and drawing compiler are incomplete (S4).
- Full architectural analysis, presentation/review workflows remain partial (S5).
- IFC import/export round-trip certification is not complete (S6).
- Collaboration, AI Copilot, production scaling and privacy workflows remain roadmap work (S7).
- PostgreSQL/PostGIS integration is not equivalent to having every test execute against PostgreSQL/PostGIS.

## Change rule

When implementation changes the architectural truth, update this document and the relevant focused architecture document in the same PR as the change. Architectural documentation is a contract with the codebase, not a future-state marketing document.
