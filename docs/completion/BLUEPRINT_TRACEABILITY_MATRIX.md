# Blueprint Traceability Matrix (Initial Audit)

Status meanings: **Partial** = implementation exists but acceptance criteria are incomplete or unverified; **Blocked** = unable to verify in this sandbox; **Missing/Gap** = known capability not present at required depth. This is a baseline, not a claim that every sub-requirement was independently tested.

| Phase | Blueprint area | Workspace evidence | Audited status | Main remaining gate |
|---:|---|---|---|---|
| 0 | Repository audit | Phase 0 report, project structure | Partial | Dependency/license/SBOM audit |
| 1 | Development foundation | Compose, Makefile, API config | Partial | Clean install, pinned locks, container verification |
| 2 | Identity/project core | `main.py`, models, auth/dependencies, tests | Partial | PostgreSQL integration, tenant-isolation tests, sessions/invites |
| 3 | World Model | world_model domain, revision model | Partial | DB-backed concurrency and artifact provenance tests |
| 4 | Requirements intelligence | requirements service/routes/schemas | Partial | Document ingestion, persisted extraction, UI integration |
| 5 | Assumptions/clarifications | assumptions domain/model | Partial | Unified revision lifecycle and UI loop |
| 6 | Decision runtime | provider contract/routes/tests | Partial | Persisted decision audit, verified live provider contract |
| 7 | Workflow runtime | workflow models/routes/tests | Partial | Atomic claims, leases/recovery, handler execution, DB integration |
| 8 | Geometry engine | geometry engine/routes/tests | Partial | Persisted artifact, revision binding, polygon/mesh validation |
| 9 | 3D viewer | `GeometryViewer.tsx`, frontend shell | Partial / Blocked | WebGL viewer confirmation, build and browser verification |
| 10 | Quantities/cost | estimates engine/routes/tests | Partial | Geometry-derived quantities, immutable rate/estimate persistence |
| 11 | Structural workflow | structure engine/routes/tests | Partial | Persisted/verified geometry-linked concepts; engineer review boundary |
| 12 | Regulatory engine | regulatory engine/routes/tests | Partial | Authoritative versioned rule library, persistence and applicability review |
| 13 | Change impact | graph engine/routes/tests | Partial | Persistent dependencies and atomic stale propagation hooks |
| 14 | Validation/evidence | validation engine/routes/tests | Partial | Persisted immutable runs and cross-domain validators |
| 15 | Review/deliverables | review routes/models/tests | Partial | Complete package assembly, source verification, immutable exports |
| 16 | Frontend integration | React/Vite shell, package manifest | Partial / Blocked | Dependency lock/install, build, complete domain UI/API flows |
| 17 | Testing/release | CI, preflight, release docs | Partial / Blocked | DB/E2E/security/container/deployment gates |

## Cross-cutting acceptance criteria not yet proven

- One persisted canonical World Model revision drives downstream artifacts.
- Derived artifacts are immutable/versioned and can be independently verified against dependencies.
- Upstream mutations atomically mark dependent outputs stale.
- End-to-end workflow executes real handlers and survives process restart.
- UI supports the main journey without direct API/database intervention.
- Clean extraction and documented setup produce a working application.
