# Phase 13 — Change Impact & Stale Propagation (partial)

## Delivered
- Typed dependency graph input and validation for unique artifact IDs, known dependencies, and known changed IDs.
- Deterministic transitive downstream impact analysis with dependency paths.
- Affected downstream artifacts are returned as `stale`; unrelated artifacts are listed separately.
- Authenticated, project-membership-scoped `POST /api/v1/change-impact/analyze` endpoint.
- Cycle-safe traversal; analysis does not mutate or claim to persist artifacts.

## API
`POST /api/v1/change-impact/analyze`

Request includes `project_id`, `changed_artifact_ids`, `new_source_revision`, and the artifact dependency snapshot. Response explicitly states `impact_analysis_only` and that no artifact was recomputed or independently verified.

## Verification
- API test suite: 49 passed.
- Four existing FastAPI `on_event` deprecation warnings.

## Remaining gates
- Persisted dependency registry and immutable change-event history.
- Atomic stale-state propagation and concurrency control.
- Automatic wiring to World Model, geometry, estimate, structural, and regulatory mutations.
- Verified source revision/hash checks, recomputation scheduling, and recovery semantics.
- PostgreSQL integration and browser-level tests.

This phase is partial and not production-ready. No regulatory or engineering approval is implied.
