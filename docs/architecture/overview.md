# AIrchitect Architecture Overview

**Status:** repository truth as of `main` at `c6ed41bb9a411a495892b15d0e9a94483fb7de9c` (Phase 28 merge).

This document describes what exists today. Planned roadmap capabilities are explicitly marked as planned and must not be treated as implemented.

## Product boundary

AIrchitect is a modular-monolith, AI-assisted architectural feasibility and design workspace. The current implementation is strongest in project/version management, requirements and assumptions, a persisted World Model, artifact versioning/dependencies, design generation, geometry/CAD infrastructure, change-impact propagation, validation, and a React workspace shell. The complete Site → Program → Concepts → Building → Drawings → Analysis → Review → BIM/CAD product described in the roadmap is not yet implemented end-to-end.

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

The backend application entrypoint is `apps/api/app/main.py`. Shared SQLAlchemy models currently live in `apps/api/app/db/models.py`; the roadmap intentionally keeps this centralized until extraction is justified by complexity.

## Backend domains currently present

The current `apps/api/app/domains/` tree includes AI, assumptions, CAD, change impact, decisions, design, engineering, estimates, evidence, foundation, geometry, identity, lifecycle, projects, regulatory, and requirements. The repository also contains core infrastructure, database configuration, dependencies, and a dedicated CAD worker under `apps/api/app/cad_worker/`.

Domain code should own domain behavior. Routes/adapters should not become alternate sources of truth for canonical state.

## Persistence and canonical state

The current persistence model includes:

- organizations, memberships, projects and project versions;
- building briefs, requirements and assumptions;
- `WorldModelRevision` with a persisted model payload and hash;
- `ArtifactVersion` and `ArtifactDependency`;
- design generation runs and constraints;
- workflow/task/event state and audit-oriented records;
- geometry, engineering, estimate, regulatory, evidence and decision records.

The World Model and versioned artifact/dependency systems are the foundation for the roadmap's canonical-state architecture. They are not permission to mutate arbitrary JSON from the UI: future mutations must go through validated commands.

## Dependency and change impact

Phase 27 established the authoritative artifact dependency graph and hash-guarded change-impact propagation. It records directed artifact dependencies, detects/guards cycles, propagates staleness, and protects version/project boundaries. Phase 28 added workspace visibility and release validation around that infrastructure.

Current propagation marks affected artifacts stale. It does **not** by itself constitute a complete dependency-aware regeneration scheduler.

## Frontend truth

The current web application is a React/TypeScript/Vite application. `apps/web/src/main.tsx` still owns authentication, organization/project loading, navigation, project creation and substantial workspace state. A `FoundationWorkspace` feature exists and is the current project workspace surface.

The target roadmap architecture is a professional workspace with explicit application shell, feature modules, shared UI, state stores, API adapters and renderer/map adapters. That restructuring is planned incrementally; it is not represented as already complete.

## API and contracts

The FastAPI application exposes authentication, organization/project, requirements, World Model, artifacts, design, geometry, validation, evidence, workflow and change-impact capabilities through domain routes. API contracts are currently represented by FastAPI/Pydantic schemas rather than a generated frontend client. Contract testing and a generated client remain roadmap work.

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

## Known architectural gaps

- Site World Model and canonical site command flow are not yet implemented.
- Provider adapters/terms registry are not yet a unified capability layer.
- Program, envelope and deterministic concept-generation workflow is incomplete.
- Universal command bus, edit history and runtime regeneration are not yet unified.
- Full semantic building model, unified 2D/3D renderer and drawing compiler are incomplete.
- Analysis/presentation/review workflows are partial.
- IFC import/export round-trip certification is not complete.
- Collaboration, AI Copilot, production scaling and privacy workflows remain roadmap work.
- PostgreSQL/PostGIS integration is not equivalent to having every test execute against PostgreSQL/PostGIS.

## Change rule

When implementation changes the architectural truth, update this document and the relevant focused architecture document in the same PR as the change. Architectural documentation is a contract with the codebase, not a future-state marketing document.
