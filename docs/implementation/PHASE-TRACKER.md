# MVP Phase Tracker

| Phase | Name | Status | Exit evidence |
|---:|---|---|---|
| 0 | Repository Audit | Partial | Phase report exists; master audit/traceability now added; SBOM/license gates remain. |
| 1 | Development Foundation | Partial | Compose/runtime scaffolding exists; clean install, lockfiles, migration wiring and container validation remain. |
| 2 | Identity and Project Core | Partial | Auth, org/project APIs and models exist; PostgreSQL integration, tenant-isolation tests, revocation/invites remain. |
| 3 | World Model | Partial | Typed schema and revision routes/models exist; persisted concurrency and downstream artifact binding remain. |
| 4 | Requirements Intelligence | Partial | Deterministic parser and endpoint exist; document extraction and full UI loop remain. |
| 5 | Assumptions and Clarifications | Partial | Assumption lifecycle/API exists; unified revision/stale lifecycle and UI remain. |
| 6 | Decision Runtime | Partial | Provider contract and deterministic fallback exist; durable audit and live provider contract verification remain. |
| 7 | Workflow Runtime | Partial | Persisted DAG/task APIs exist; atomic claims, leases/recovery and handler execution remain. |
| 8 | Geometry Engine | Partial | Deterministic cuboid massing exists; artifact persistence, revision binding and polygon support remain. |
| 9 | 3D Viewer | Partial / Blocked | Interactive viewer shell exists; WebGL confirmation, frontend build and browser QA remain. |
| 10 | Quantities and Cost | Partial | Deterministic sourced-rate estimator exists; persisted geometry-derived quantities and immutable records remain. |
| 11 | Structural Workflow | Partial | Conceptual structural output exists; verified geometry binding and engineering review remain. |
| 12 | Regulatory Engine | Partial | Configurable rule evaluator exists; authoritative ruleset, applicability and persistence remain. |
| 13 | Change Impact | Partial | Dependency impact analysis exists; persistent graph and atomic mutation-driven propagation remain. |
| 14 | Validation and Evidence | Partial | Validation/evidence aggregation exists; immutable persisted cross-domain runs remain. |
| 15 | Review and Deliverables | Partial | Review and PDF/JSON endpoints exist; verified assembled immutable packages remain. |
| 16 | Frontend Integration | Partial / Blocked | React workspace shell exists; dependencies/build and full domain UI journey remain. |
| 17 | Testing and Release | Partial / Blocked | API unit suite and preflight exist; DB/E2E/security/container/deployment gates remain. |
| 18 | CAD/BIM Geometry Pipeline | In progress | Real-kernel geometry (OCCT/FreeCAD) with IFC/GLB/STEP export, an isolated bounded worker, durable job/artifact persistence, and tenant-scoped API endpoints; quantities, structural/regulatory consumers, frontend integration, and container gates remain. |

## Rules
- A phase is complete only with implementation evidence, tests, limitations, and Definition of Done confirmation.
- Never count scaffolding, placeholders, simulated progress, or unverified external data as completion.
- Keep this tracker updated as work progresses.


## Phase 2 — Identity and Project Core (in progress)
- [x] SQLAlchemy identity, organization, membership, project, audit models
- [x] Password hashing and signed expiring bearer tokens
- [x] Registration/login/current-user endpoints
- [x] Organization-scoped project CRUD (create/list/read/update)
- [x] Minimal frontend auth and project creation/listing
- [x] Security unit tests
- [ ] Full DB-backed integration tests and tenant-isolation verification
- [ ] Alembic migration execution and PostgreSQL/PostGIS validation
- [ ] Optimistic concurrency, session revocation, invite/member management

| 3 | World Model | Partially complete | Typed canonical schema, revision persistence/API, basic validation, unit tests; DB integration/concurrency gates remain |

| 4 | Requirements Intelligence | In progress / initial slice | Deterministic brief parser, authenticated analysis endpoint, tests; semantic/document extraction and UI integration remain |

| Phase 5 — Assumptions & Clarifications | Partial | Persistent assumption lifecycle and authenticated APIs implemented; 13 tests pass. DB integration, unified revision/stale propagation, and UI remain open. |

## Phase 6 — Decision Runtime (partial)
- [x] Typed provider-independent request/response contracts
- [x] Deterministic local provider
- [x] Benchmark fixture provider
- [x] Jev adapter boundary (fail-closed; live contract not configured)
- [x] Allowed-option response validation
- [x] Authenticated evaluate endpoint
- [ ] Persistent decision/audit records and full endpoint integration tests
- [ ] Live Jev contract verification, timeout/retry policy, and provider benchmark suite


## Phase 7 — Workflow Runtime (partial)
- [x] Persisted workflow and task models
- [x] Authenticated organization-scoped create/read APIs
- [x] DAG validation and dependency-aware task claiming
- [x] Task success/failure, retry-by-requeue, and workflow cancellation endpoints
- [x] Unit tests (23 total API tests pass)
- [ ] Atomic concurrent claims / worker lease and crash recovery
- [ ] Idempotency request fingerprinting and durable transition event history
- [ ] PostgreSQL migration/integration and worker-handler execution tests


## Phase 8 — Geometry Engine (partial)
- [x] Typed bounded massing request and unique option IDs
- [x] Deterministic cuboid geometry and derived area/volume/height
- [x] Canonical geometry hash and artifact ID
- [x] Authenticated geometry-generation endpoint
- [x] Unit tests (27 total API tests pass)
- [ ] Persist artifacts and bind/verify current World Model revision
- [ ] Arbitrary site polygons, orientation, boundary/setback clipping
- [ ] Robust mesh validation and viewer-ready export formats
- [ ] PostgreSQL endpoint integration and tenant-isolation tests

## Phase 9 — 3D Viewer (partial)
- [x] Authenticated project workspace entry point
- [x] API-backed geometry generation and alternative switching
- [x] Interactive canvas mesh display (orbit/zoom/reset)
- [x] Artifact metadata, source revision display, caveats, error/loading states
- [ ] WebGL/Three.js rendering, true picking, camera-fit, and floor-level geometry
- [ ] Persisted artifact retrieval with current World Model revision binding
- [ ] Frontend production build, browser smoke/automation, and end-to-end integration


## Phase 10 — Quantities and Cost (partial)
- [x] Typed quantities with units and source provenance
- [x] Versioned user-supplied SAR rate bands with low/base/high ordering
- [x] Deterministic line items, scenario subtotals, and contingency
- [x] Authenticated organization-scoped calculation endpoint
- [x] Stable estimate identity bound to geometry reference/hash and source revision
- [x] Unit tests (31 total API tests pass)
- [ ] Extract/reconcile quantities directly from persisted geometry artifacts
- [ ] Persist immutable estimates and rate schedules; stale propagation on source changes
- [ ] Saudi market calibration, QS review, PostgreSQL integration, and frontend UI

| 11 | Structural Workflow | Partial | Deterministic conceptual grid endpoint, provenance fields, explicit non-engineering checks; 37 API tests pass. Persistence, verified geometry binding, engineering analysis/review, and frontend remain open. |

| 12 | Regulatory Engine | Partial | Configurable evidence-attributed rule evaluator, explicit unknown state, authenticated project-scoped endpoint; no authoritative Saudi rule library or persistent/stale-linked evaluations. |

## Phase 13 — Change Impact & Stale Propagation
- Status: **Partial**
- Delivered: dependency graph validation, transitive downstream impact analysis, stale-result classification, authenticated project-scoped endpoint, unit tests.
- Open: persistence, atomic propagation, automatic mutation hooks, recomputation scheduling, concurrency/recovery, PostgreSQL integration.
- Report: `PHASE-13-CHANGE-IMPACT.md`

## Phase 14 — Validation & Evidence
- Status: **Partial**
- Delivered: typed evidence/check contracts, deterministic aggregation, missing/unverified evidence detection, stale hash handling, authenticated project-scoped endpoint; 54 API tests pass.
- Open: immutable persistence, independent evidence verification, persisted revision binding, cross-domain integration, stale propagation, frontend review UI, PostgreSQL integration.
- Report: `PHASE-14-VALIDATION-EVIDENCE.md`

## Phase 15 — Review & Deliverables
- Status: **Partial**
- Delivered: persisted human review records and audit event, project-scoped review listing, JSON/PDF feasibility deliverable generation, explicit validation/currentness metadata and preliminary-only disclaimer; 58 API tests pass.
- Open: immutable/content-addressed deliverable records, independent source-hash verification, assembled cross-domain package, multi-review policy, polished PDF, frontend download integration, PostgreSQL and browser E2E verification.
- Report: `PHASE-15-REVIEW-DELIVERABLES.md`

| 16 | Frontend Integration & Professional UI | Partial | Responsive graphite/stone/copper workspace shell; auth, project list/create/search, loading/error states, and existing geometry viewer entry wired to current API. shadcn config/dependencies declared. Frontend build blocked by unavailable dependency installation; browser QA and full shadcn primitive adoption remain open. |

## Phase 17 — Testing & Release Readiness
- Status: **Partial — NOT RELEASE-READY**
- Delivered: full API unit suite rerun (58 passed); release preflight script; CI job cleanup and explicit release-preflight job; documented release gates.
- Open: frontend dependency lock/install/build, DB-backed integration and tenant-isolation tests, browser E2E, production security review, container/SBOM scan, deployment rehearsal, qualified domain validation.
- Report: `PHASE-17-TESTING-RELEASE.md`


## Phase 18 — CAD/BIM Geometry Pipeline
- Status: **In progress** (S1–S10 delivered; S11–S14 open)
- Delivered:
  - S1 verified toolchain manifest and open-source licence audit (`docs/legal/PHASE-18-OPEN-SOURCE-LICENSE-AUDIT.md`).
  - S2–S7 worker protocol plus OCCT/FreeCAD geometry, IFC, GLB, and STEP export.
  - S8 capability discovery and a bounded worker runner with scratch isolation, payload limits, artifact verification, typed errors, and timeout/process-tree termination.
  - S9 persistence: `cad_job_runs` and `cad_artifacts`, content-addressed artifact storage outside PostgreSQL, and a repository that records success and failure, binds geometry to the current `WorldModelRevision`, and records validation, checks, and evidence.
  - S10 API and orchestration: four tenant-scoped endpoints (generate, read run, list artifacts, download), an orchestrator that derives all geometry server-side from a design alternative, dispatches the blocking worker to a thread so a slow kernel cannot stall the event loop, and records every invoked job as a run. Failures after invocation are recorded outcomes (201 with `FAILED`); an absent toolchain is a 503 that records nothing. Artifact bytes are streamed with persisted content type and an `ETag`, and the server's storage path is never exposed.
- Open: S11 quantities measured on the solid; S12 structural and regulatory consumers; S13 frontend GLB integration replacing fabricated browser geometry; S14 Docker/CI, parity gates against the legacy engine, and the final architecture/completion reports.
- Fixed in passing: four `error(...)` call sites passed `status=` as a keyword while `error`'s first parameter is named `status`, which raised `TypeError` instead of the intended 4xx. These were latent 500s on the design-generation, alternative-selection, and engineering-quantity paths.
- Architecture: `../architecture/PHASE-18-CAD-BIM-ARCHITECTURE.md`
- Licence audit: `../legal/PHASE-18-OPEN-SOURCE-LICENSE-AUDIT.md`
- Verification status: API suite 397 passed (40 against the real OCCT/FreeCAD worker); Ruff clean; `mypy app/domains/cad` clean; `models.py` at its 63-error pre-existing baseline; one Alembic head. Unverified: PostgreSQL, Docker, and `ifcopenshell.geom` on Python 3.14.4 (see the architecture document).

## Master completion pass — baseline update (2026-09-25)
- Re-audited workspace, phase reports, API source/tests, frontend manifest, and environment setup.
- Replaced contradictory summary rows with evidence-based partial/blocked statuses.
- Fixed API lifespan deprecation, session factory reuse, direct SQLAlchemy JSON imports, and non-local weak-secret startup validation.
- API test suite: 58 passed. Frontend install timed out; database/E2E/deployment gates remain unverified.
- Detailed artifacts: `docs/completion/`.
