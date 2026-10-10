# Phase 27 — Dependency-Aware Feasibility & Change Propagation

**Status:** Implemented; PR #9 is open and has passing CI.
**Branch:** `feat/phase-27-dependency-aware-propagation`
**Pull request:** https://github.com/RayAKaan/AIrchitect/pull/9
**Final verified CI run:** [#342](https://github.com/RayAKaan/AIrchitect/actions/runs/38084423669) — PASS on implementation commit `89d8dad2bbf9325304d925da47e36fae6e8ee3f7`.

## Delivered

- Added a persisted, project-version-scoped dependency graph API based on `ArtifactVersion` and `ArtifactDependency`; clients cannot submit an authoritative graph for mutation.
- Added deterministic shortest-path transitive impact traversal with stable ordering, multiple roots, and cycle protection.
- Detects and excludes cross-project/version dependency edges from traversal, exposing a review-required integrity status instead of crossing scope.
- Added an authenticated propagation API with a required expected World Model SHA-256; stale client state receives HTTP 409 before any mutation.
- Atomically updates affected ArtifactVersion rows and linked design, geometry, quantity, cost, structural, regulatory, validation, and deliverable lifecycle statuses. Artifact payloads and hashes are not rewritten.
- Records changed roots, source hash, paths, affected IDs, reason, and scope diagnostics in audit events.
- Hooks canonical World Model persistence so a changed hash invalidates artifacts bound to the superseded revision and marks prior successful/in-flight CAD runs stale.
- Added unit tests and API integration tests for transitive propagation, unaffected artifacts, automatic World Model invalidation, stale-hash conflicts, audit lineage, and cross-version edge isolation.
- Updated the Phase 27 tracker and release-preflight requirements.

## Final CI verification — PASS

GitHub Actions run #342 completed successfully across all four jobs:

- **API:** Ruff passed; **449 passed, 40 skipped, 2 warnings**; PostgreSQL migration upgrade/downgrade/upgrade passed; API Docker image build passed.
- **Web:** lint passed; **17 tests passed**; production build and web Docker image build passed.
- **Docker Compose:** images built; stack started; database-aware readiness and API smoke checks passed; teardown passed.
- **Release preflight:** passed, including CAD/BIM licence policy, the ten-case requirements benchmark (precision 1.0, recall 1.0, F1 1.0), and required phase documentation.

The benchmark remains limited to its ten committed fixtures. The CI run verifies automated tests and deployment smoke checks, not native production-host CAD execution or universal CAD/BIM interoperability.

## Boundaries and remaining gates

- Stale propagation does not recompute artifacts or enqueue a workflow; it explicitly reports `recomputation_scheduled: false`.
- Artifact payloads and output hashes remain immutable; lifecycle status and audit metadata change.
- Cross-scope dependency edges are excluded and flagged for review, not repaired automatically.
- Current source hashes do not certify architectural correctness, structural adequacy, regulatory compliance, fire/life safety, or constructability.
- Phase 22 native-host CAD smoke evidence and complete redistribution/source-material notices plus qualified legal sign-off remain open release gates.

**Merge status:** PR #9 is open and not merged. Review and merge manually.
