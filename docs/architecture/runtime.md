# Production Runtime Operations

## Regeneration worker

The regeneration worker is a single-iteration deterministic worker supervised by an outer process loop. It claims durable jobs with a lease, executes handlers outside the claim transaction, and commits successful artifact output atomically. Handler failures are rolled back before retry/failure state is persisted.

Run locally from the repository root after installing the API package:

```bash
python scripts/run_regeneration_worker.py --worker-id local-regeneration-1
```

Production deployments should run one or more long-lived worker processes under an external supervisor/container orchestrator. The worker does not run Alembic and never creates tables implicitly.

## Release authority

A release is server-authoritative. The release gate evaluates required current artifacts, output hashes, provenance, and dependency integrity. The release manifest is deterministic and hashed from canonical artifact identity, provenance, output hashes, and dependency lineage.

The release package composes those two contracts and verifies the manifest hash before returning it. A client must never infer release readiness from cached artifact state or UI state.

## Runtime API

- `GET /api/v1/health` — database-backed runtime readiness probe.
- `GET /api/v1/projects/{project_id}/versions/{version_ref}/release-readiness` — server-authoritative release blockers.
- `GET /api/v1/projects/{project_id}/versions/{version_ref}/release-manifest` — deterministic release manifest plus `X-Release-Manifest-Hash`.
- `GET /api/v1/organizations/{organization_id}/runtime/metrics` — organization-scoped operational queue metrics.

Project endpoints preserve existing project authorization boundaries. Organization metrics require organization membership.

## Operational signals

Monitor:

- queued workflow/regeneration work;
- running work and lease expiry;
- retry volume;
- terminal failures;
- oldest queued work;
- release blockers caused by stale, missing, failed, unknown, blocked, invalid dependencies, or provenance-invalid artifacts;
- runtime readiness failures.

Metrics are operational projections only and never determine canonical state.
