# Prioritized Implementation Gaps

## P0 — Required for a credible integrated MVP

1. Reproducible frontend dependency resolution (pin versions, commit lockfile, successful install/build).
2. Alembic migration baseline and verified PostgreSQL startup; remove reliance on `create_all` outside local mode.
3. Persistent canonical World Model revision as the authoritative source for downstream work.
4. Persist geometry, quantities, estimates, structural concepts, regulatory runs, validation runs, and export metadata with revision/hash provenance.
5. Cross-domain orchestration handlers that call actual services and persist outputs.
6. Stale propagation from upstream mutations through persisted dependency edges.
7. Complete primary frontend journey wired to actual API state.
8. Tenant isolation, auth, idempotency, and workflow recovery integration tests.

## P1 — Trust, quality, and operational robustness

1. Worker-safe claims, lease expiry, retries/backoff, cancellation semantics, transition history.
2. Content-addressed artifact storage and independently verified source hashes.
3. Explicit rate schedule lifecycle and missing-rate behavior; no invented market values.
4. Ruleset applicability/effective-date handling and authoritative-source workflow.
5. Review policy, comment/decision history, and immutable deliverable snapshots.
6. Structured logs, correlation IDs, readiness checks, worker health and useful operational errors.
7. Accessible, responsive, coherent shadcn-based UI with real loading/error/empty states.

## P2 — Improvements after core acceptance

1. Arbitrary polygon geometry, orientation, setback clipping, richer alternatives.
2. Advanced quantity categories and cost sensitivity analysis.
3. Multi-review workflows and report layout refinement.
4. Browser visual regression, performance budgets, SBOM and dependency scanning.
5. Optional provider integrations (Jev/LLM) behind documented contracts and fail-closed behavior.

## External/qualified gates

- Saudi regulatory rules must be verified against authoritative, current sources and qualified review.
- Structural safety, capacity, code compliance, and foundations require qualified engineering methods/review.
- Construction rate calibration requires credible, dated, geographically applicable data and QS review.
- Production deployment requires real secrets, infrastructure, monitoring, backups, and operational rehearsal.
