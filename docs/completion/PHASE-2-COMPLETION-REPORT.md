# Phase 2 Completion Report

**Phase:** Computational Design Engine + Persisted Geometry + Professional 3D + Alternative Search  
**Date:** 2026-09-25  
**Repository baseline:** Phase 1 at `ff81790`, preserved and extended in place  
**Overall result:** **PASS for the implemented and locally executable Phase 2 scope**, with explicitly listed environment verification gaps and known limitations. This is not a production-readiness, regulatory, engineering-certification, or construction-suitability claim.

## 1. Executive result — PASS

Phase 2 is implemented end to end from the immutable ProjectVersion and resolved canonical World Model through formal design constraints, deterministic multi-strategy search, persisted alternatives, typed persisted Geometry IR, validation, version-scoped APIs, and an R3F design workspace. The final local verification passed 90 backend tests, Ruff, Python compilation, six frontend unit tests, TypeScript, production build, one real Chromium Playwright journey, and the SQLite migration cycle.

## 2. Scope boundaries — PASS

The implementation covers only Phase 2 design alternatives and conceptual geometry. It does not add Phase 3/4 quantity, cost, structural analysis, regulation/evidence conclusions, deliverables, or orchestration. Parking is a capacity metric with `geometry_status=NOT_GENERATED`; structural grids and cores are explicitly preliminary and not for construction.

## 3. Phase 1 preservation — PASS

The implementation extends the existing repository, models, artifact infrastructure, authentication, project/version lifecycle, TanStack Query frontend, and canonical World Model. It does not create a separate application or parallel canonical state. The original Phase 1 test suite remains included in the 90 passing backend tests.

## 4. Source-based architecture audit — PASS

The existing repository was audited before Phase 2 changes. Decisions and interface findings are documented in `docs/implementation/PHASE-2-IMPLEMENTATION-AUDIT.md`.

## 5. Canonical resolution chain — PASS

Every design endpoint resolves authenticated project/version ownership with `resolve_project_version(...)` and obtains inputs with `resolve_world_model(...)`. The engine receives a resolved `WorldModelRevision`; it does not accept client-authored geometry, vertices, dimensions, or renderer buffers.

## 6. Formal constraint model — PASS

`DesignConstraintResolver` produces normalized `HARD`, `PREFERRED`, `FLEXIBLE`, and `UNKNOWN` constraints with parameter, value, unit, operator, severity, rationale, source reference, and provenance. Focused tests verify classification and unknown retention.

## 7. Conflict and unsupported-topology handling — PASS

Unbounded/conflicting constraints fail with actionable design error codes. Unsupported canonical non-rectangular site topology returns `UNSUPPORTED_SITE_TOPOLOGY` rather than silently reducing the boundary. Unknown boundaries use an explicitly recorded, area-preserving rectangular design approximation.

## 8. Versioned engine configuration — PASS

The immutable configuration records design engine, configuration, and geometry-engine versions plus bounded defaults and tolerances. Its canonical serialization contributes to generation and design hashes.

## 9. Deterministic search space — PASS

The resolver builds explicit search variables for floor count, footprint ratio, target GFA factor, aspect ratio, setbacks, and floor height. Preferred values, allowed values/ranges, source classification, assumptions, and unknowns remain machine-readable.

## 10. Strategy implementation — PASS

Balanced, Compact, and Low-Rise strategies generate deterministic candidate sets. Courtyard is not faked. The strategy implementations share the platform constraint and validation model while carrying distinct objectives, parameter profiles, and version identifiers.

## 11. Material diversity and deduplication — PASS

Generation chooses the best valid materially distinct candidate for each available strategy and hashes the complete candidate parameter/metric signature for deduplication. The normal six-floor Riyadh journey persists three alternatives with different footprints, GFA/coverage trade-offs, and/or floor profiles.

## 12. Candidate validation and reasoning — PASS

Candidates persist constraint results, invalid reasons, assumptions, unknowns, deviations, trade-offs, scoring inputs, and computation-derived reasoning. No LLM is used to invent geometry or explanation. Hard failures are distinguished from preferred deviations in focused tests.

## 13. Deterministic design hashes — PASS

A design hash is derived from the exact World Model hash, strategy ID/version, canonical parameters, engine version, and config version. Random database IDs are excluded. Repeated identical generation returns the existing completed run and artifacts.

## 14. Alternative persistence — PASS

`DesignAlternative` persists relational project/version/world/run lineage plus strategy, parameter, metric, constraint, reasoning, assumption, unknown, trade-off, provenance, engine/config version, input hash, design hash, lifecycle status, and selection fields.

## 15. Typed Geometry IR — PASS

The platform IR represents the site, setbacks, masses, floor plates, cores, preliminary structural grids, dimensions, parking status/capacity, orientation status, transforms, dimensions, units, labels, source design hash, and metadata. It contains domain geometry rather than Three.js objects or screenshots.

## 16. Deterministic geometry generation — PASS

`MassingGeometryEngine` derives geometry only from a validated design candidate and the resolved design context. Geometry IR source references use stable design hashes. Geometry hashes are computed from canonical IR, geometry-engine version, and design hash.

## 17. Geometry validation — PASS

`GeometryValidator` checks positive dimensions, site containment, object references, floor count, footprint, GFA, coverage, and height consistency within versioned tolerances. All geometry is generated and validated before alternatives are inserted, preventing known validation failures from leaving partial valid artifacts.

## 18. Artifact lineage — PASS

Lineage is explicit across Project → ProjectVersion → WorldModelRevision/hash → generation run/constraints → DesignAlternative/design hash → GeometryArtifact/geometry hash. Existing `ArtifactVersion` and `ArtifactDependency` infrastructure links every geometry artifact to its design alternative.

## 19. Generation lifecycle — PASS

Generation runs record `GENERATING`, `COMPLETED`, and `FAILED` states; staged progress; request/completion timestamps; exact input hash; engine/config versions; generated alternative IDs; and actionable failure codes/messages. The frontend exposes completed stages.

## 20. Idempotency and retry — PASS

Identical completed requests return the same generation ID with `idempotent=true`; a newly completed request returns `false`. Failed runs remain durable and a later identical request retries using the stable generation identity after clearing prior diagnostics. A simulated unexpected runtime failure verifies rollback, durable failure state, zero partial artifacts, and successful retry.

## 21. Concurrency safety — KNOWN LIMITATION

Database uniqueness protects `(project_version_id, generation_key)`, and an observed `GENERATING` run returns `DESIGN_GENERATION_IN_PROGRESS`. Selection locks version alternatives where supported. True simultaneous-request behavior and PostgreSQL row-lock semantics were not executable in this environment, so no PostgreSQL concurrency-pass claim is made.

## 22. Failure handling, audit, and logging — PASS

Known design failures and unexpected exceptions produce durable failed runs. Unexpected work is rolled back before the failure record is committed. Generation, alternative, geometry, invalidation, failure, and selection actions emit audit events; major engine stages emit structured logs with project/version/run/artifact identifiers.

## 23. Staleness and multiversion behavior — PASS

A changed World Model hash within the same version marks earlier alternatives, geometry, and associated artifact versions stale. Creating V2 does not stale or re-associate V1 artifacts. API tests verify that V2 starts with no V1 alternatives, generates new hashes, and leaves V1 hashes/statuses unchanged.

## 24. Version-specific human selection — PASS

Selection is scoped to one authenticated ProjectVersion, clears another selection only in that version, rejects stale/non-valid alternatives, records actor/time/reason, and explicitly states that selection is a human direction rather than approval, certification, or objective superiority.

## 25. Tenant authorization — PASS

All Phase 2 endpoints pass through native authentication and organization/project/version authorization. Cross-tenant access is non-disclosing. API tests verify a second organization receives `404 PROJECT_NOT_FOUND` for another tenant's design collection.

## 26. API surface — PASS

Seven version-scoped Phase 2 paths provide generation, generation status, alternative list/detail, exact persisted geometry, comparison, and selection. Generated OpenAPI contains 60 total paths and 67 operations, including all seven Phase 2 paths.

## 27. Design workspace — PASS

A dedicated React/TanStack Query workspace is integrated as the **Design** tab of the existing Foundation workspace. It handles committed-version gating, generation, loading/error/empty states, progress, strategy cards, metrics, constraints, computed reasoning, trade-offs, provenance, current/stale status, comparison, and selection.

## 28. Professional R3F viewer — PASS

The viewer consumes exact persisted Geometry IR. It provides orbit, pan, zoom, fit, reset, six camera presets, floor isolation, solid/wireframe/ghost modes, clipping control, site/setback/grid/core/floor rendering, persisted dimensions, lighting, and geometry-hash display. It does not reconstruct authoritative geometry from summary metrics.

## 29. Comparison, accessibility, and responsive behavior — PASS / KNOWN LIMITATION

The comparison view presents the explicit metrics of all three alternatives and states that no single optimum is claimed. Controls use accessible buttons, labels, selected/pressed states, status text, and non-color-only stale/error wording. Responsive layout rules exist; the executed visual QA covered desktop Chromium, not a separate physical mobile/browser matrix.

## 30. Migration verification — PASS on SQLite

Revision `20260925_0003` creates generation/constraint storage and expands alternatives/geometry with SQLite-compatible batch alteration. Fresh `upgrade head → downgrade 0002 → upgrade head` passed. A `0002` database containing legacy design and geometry rows upgraded successfully; legacy rows were retained and normalized to archived/legacy metadata without design-hash collisions.

## 31. Backend verification — PASS

Final executed commands/results:

- `pytest -q` — **90 passed**.
- `ruff check .` — **passed**.
- `python -m compileall -q app` — **passed**.
- Focused coverage includes constraints, strategy determinism/diversity, hard/preferred semantics, persistence/lineage, Geometry IR and hashes, idempotency, durable failure/retry, staleness, API generation/list/geometry/comparison/selection, tenant isolation, and V1/V2 separation.

Strict whole-repository mypy is not claimed; the repository retains its pre-existing mypy error baseline.

## 32. Frontend, E2E, and visual verification — PASS

Final executed results:

- `npm run lint` (`tsc -b`) — **passed**.
- `npm test` — **6 passed** across two Vitest files.
- `npm run build` — **passed** (655 modules transformed).
- `npm run test:e2e` — **1 Chromium Playwright journey passed**.
- The real browser journey registered a tenant, created a project, analyzed/committed V1, generated three alternatives, loaded WebGL geometry, changed camera/render/floor/section controls, compared alternatives, inspected provenance, and selected a direction.
- Manual visual inspection of the captured final scene found coherent desktop hierarchy, readable controls/provenance, visible persisted mass/floor/core/site geometry, and no clipping or layout blocker. Evidence: `docs/completion/phase2-visual-qa.png`.
- Runtime production dependency audit (`npm audit --omit=dev`) reported **0 vulnerabilities**. The Vite build warns that the main bundle is approximately 1.16 MB before gzip; code splitting is a performance follow-up, not a correctness blocker.

## 33. Not run and known limitations — NOT RUN / KNOWN LIMITATION

- **PostgreSQL/PostGIS:** NOT RUN because Docker, `psql`, and `pg_isready` are unavailable. No PostgreSQL claim is made.
- **True concurrent requests:** NOT RUN against PostgreSQL; uniqueness/in-progress handling is implemented and sequential idempotency is tested.
- **Cross-browser/mobile visual matrix:** NOT RUN; Chromium desktop was executed.
- **Courtyard/non-rectangular generated mass topology:** intentionally unsupported rather than approximated as authoritative.
- **Parking layout:** intentionally not generated; only capacity/status is represented.
- **Orientation when unknown:** retained as unknown; no north arrow is fabricated.
- **Structural grid/core:** conceptual, preliminary, human-review-required, and not engineering-approved.
- **Production readiness/regulatory authority/professional certification:** not claimed.

## 34. Final disposition — PASS WITH DISCLOSED VERIFICATION GAPS

The requested Phase 2 flow is implemented and passes all locally executable acceptance checks. No known local correctness blocker remains. The two material verification gaps are PostgreSQL/concurrent-load execution and a broader browser/device visual matrix; they are disclosed rather than converted into unsupported claims. Phase 1 remains canonical, alternatives remain derived and version-specific, and all displayed geometry comes from persisted validated Geometry IR.
