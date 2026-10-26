# Production Runtime Operations

## Regeneration worker

The regeneration worker is a single-iteration deterministic worker supervised by an outer process loop. It claims durable jobs with a lease, executes handlers outside the claim transaction, and commits successful artifact output atomically. Handler failures are rolled back before retry/failure state is persisted.

Run locally from the repository root after installing the API package:

```bash
python scripts/run_regeneration_worker.py --worker-id local-regeneration-1
```

Production deployments should run one or more long-lived worker processes under an external supervisor/container orchestrator. The worker does not run Alembic and never creates tables implicitly.

## Runtime API

- `GET /api/v1/projects/{project_id}/versions/{version_ref}/release-readiness` — server-authoritative release blockers.
- `GET /api/v1/organizations/{organization_id}/runtime/metrics` — organization-scoped operational queue metrics.

Both endpoints require authenticated access and preserve existing project/organization authorization boundaries.

## Operational signals

Monitor:

- queued workflow/regeneration work;
- running work and lease expiry;
- retry volume;
- terminal failures;
- oldest queued work;
- release blockers caused by stale, missing, failed, unknown, blocked, or provenance-invalid artifacts.

Metrics are operational projections only and never determine canonical state.
